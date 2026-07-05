from app.agents.base_agent import BaseAgent
from app.models.response_models import AgentResult, SourcedStep
from app.tools.firestore_tool import query_facilities
from app.tools.maps_tool import find_nearby_hospitals, find_nearby_places, get_distance, reverse_geocode, _is_coordinate_pair


# Non-medical place categories the Facility Agent can also find. Each maps to a
# Google Places `type` (or "" to rely on keyword) plus a search keyword + label.
_PLACE_CATEGORIES = {
    "gym":        {"type": "gym",     "keyword": "gym fitness center",     "label": "gym"},
    "yoga":       {"type": "gym",     "keyword": "yoga studio",            "label": "yoga studio"},
    "pool":       {"type": "",        "keyword": "swimming pool",          "label": "swimming pool"},
    "playground": {"type": "park",    "keyword": "playground",             "label": "playground"},
    "park":       {"type": "park",    "keyword": "park garden",            "label": "park"},
    "stadium":    {"type": "stadium", "keyword": "stadium",                "label": "stadium"},
    "sports":     {"type": "",        "keyword": "sports complex ground turf court", "label": "sports facility"},
}

# Ordered keyword checks — first match wins (specific before general).
_CATEGORY_CHECKS = [
    (("gym", "fitness", "weight train", "workout place", "crossfit"), "gym"),
    (("yoga", "pilates"), "yoga"),
    (("swimming", " swim", "swim ", "pool"), "pool"),
    (("playground", "play ground", "play area"), "playground"),
    (("park", "garden", "jog", "jogging", "run near", "running track", "walk near",
      "walking track", "morning walk", "evening walk", "cycling", "cycle track", "trail"), "park"),
    (("stadium",), "stadium"),
    (("sports", "sport ", "turf", "badminton", "tennis", "basketball", "football ground",
      "cricket ground", "cricket net", "sports complex", "sports club"), "sports"),
]


def _detect_place_category(text: str) -> dict | None:
    """Return a _PLACE_CATEGORIES entry if the text is asking for a non-medical
    place (gym, park, pool, etc.), else None (treat as a hospital/clinic query)."""
    t = (text or "").lower()
    for keys, cat in _CATEGORY_CHECKS:
        if any(k in t for k in keys):
            return _PLACE_CATEGORIES[cat]
    return None


FACILITY_CONTEXT_SCHEMA = {
    "type": "object",
    "properties": {
        "specialty_needed": {
            "type": "string",
            "description": "Medical specialty needed e.g. oncology, cardiology, general_medicine, psychiatry, neurology",
        },
        "city": {"type": "string", "description": "City name, empty string if not mentioned"},
        "state": {"type": "string", "description": "Indian state name, empty string if not mentioned"},
        "preferred_scheme": {
            "type": "string",
            "description": "Government scheme ID if user mentioned one e.g. pmjay, cghs, esis — empty string if none",
        },
    },
    "required": ["specialty_needed", "city", "state", "preferred_scheme"],
}

RANK_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "facility_id": {"type": "string"},
            "why_recommended": {"type": "string"},
            "what_to_do": {"type": "string"},
        },
        "required": ["facility_id", "why_recommended", "what_to_do"],
    },
}


class FacilityAgent(BaseAgent):
    name = "facility_agent"
    description = "Finds hospitals and clinics relevant to the user's healthcare need"

    async def run(self, context: dict) -> AgentResult:
        self.logger.info("FacilityAgent starting")
        user_message = context.get("user_message", "")

        # Use typed params from orchestrator first; fall back to Gemini extraction
        condition  = context.get("condition", "")
        location   = context.get("location", "") or ""
        specialty  = context.get("specialty", "")
        coordinates = context.get("coordinates")  # {"lat": ..., "lng": ...} if available

        # If the location arrived as a "lat,lng" string, treat it as coordinates.
        if not coordinates and _is_coordinate_pair(location):
            lat, lng = (float(x.strip()) for x in location.split(","))
            coordinates = {"lat": lat, "lng": lng}

        # One reverse-geocode so the Firestore city filter agrees with the Maps proximity
        # search — avoids the "coords say X, city string says Y" split. Cached per session.
        derived_city = ""
        if coordinates and coordinates.get("lat") and coordinates.get("lng"):
            derived_city = await self._city_for_coords(coordinates)

        # A coordinate string is never a usable city name for Firestore.
        text_location = "" if _is_coordinate_pair(location) else location

        # Non-medical places (gym, park, pool, playground, sports) take a Places-only
        # path — Firestore holds hospitals only, so ranking them here would be wrong.
        category = _detect_place_category(user_message) or _detect_place_category(condition) or _detect_place_category(specialty)
        if category:
            self.logger.info(f"FacilityAgent: place category '{category['label']}'")
            return await self._find_places(category, coordinates, text_location, derived_city)

        # Only call Gemini extraction if we have no typed params
        if not condition and not specialty:
            facility_context = await self._extract_context(user_message, text_location or derived_city)
            self.logger.info(f"Fallback extraction: {facility_context}")
            specialty = facility_context.get("specialty_needed") or ""
            city  = facility_context.get("city") or text_location or derived_city or ""
            state = facility_context.get("state") or ""
            scheme = facility_context.get("preferred_scheme") or ""
        else:
            # Map condition to specialty if not already specified
            if not specialty and condition:
                specialty = await self._condition_to_specialty(condition)
            city  = text_location or derived_city or ""
            state = ""
            scheme = ""

        # Step 2: Query Firestore — try with city first, fall back to state
        facilities = await query_facilities(
            city=city or None,
            state=state or None,
            specialty=specialty or None,
            accepts_scheme=scheme or None,
        )

        # Fallback: if nothing found with specialty filter, broaden search
        if not facilities and specialty:
            self.logger.info("No results with specialty filter, broadening search")
            facilities = await query_facilities(city=city or None, state=state or None)

        # Last resort: return all facilities
        if not facilities:
            self.logger.warning("No location match, returning all facilities")
            facilities = await query_facilities()

        if not facilities:
            return AgentResult(agent_name=self.name, steps=[], raw_data=[])

        # Step 3: Rank with Gemini
        ranked = await self._rank_facilities(facilities, user_message, specialty)

        # Step 4: Enrich top Firestore results with live Maps data
        # Use coordinates if available (more accurate), else city name
        user_location = city or location or ""
        maps_hospitals = []
        if coordinates and isinstance(coordinates, dict):
            lat, lng = coordinates.get("lat"), coordinates.get("lng")
            if lat and lng:
                maps_hospitals = await find_nearby_hospitals(
                    location=f"{lat},{lng}",
                    specialty=specialty,
                    max_results=5,
                )
        elif user_location:
            maps_hospitals = await find_nearby_hospitals(
                location=user_location,
                specialty=specialty,
                max_results=5,
            )

        # Step 5: Build SourcedSteps (deduplicate by facility_id)
        facility_map = {f["id"]: f for f in facilities}
        steps = []
        step_num = 1
        seen_ids: set[str] = set()

        for item in ranked:
            fid = item.get("facility_id", "")
            if fid in seen_ids:
                continue
            seen_ids.add(fid)
            facility = facility_map.get(fid)
            if not facility:
                continue

            source_url = facility.get("website") or facility.get("source_url", "")
            detail = f"{item['why_recommended']} — {item['what_to_do']}"

            # Attach distance if Maps data available
            distance_km = None
            ref_location = (
                f"{coordinates['lat']},{coordinates['lng']}" if coordinates
                else user_location
            )
            if ref_location:
                facility_address = f"{facility['name']}, {facility.get('city', '')}"
                dist = await get_distance(ref_location, facility_address)
                if dist:
                    detail += f" | Distance: {dist['distance_text']} ({dist['duration_text']} by road)"
                    try:
                        distance_km = float(dist["distance_text"].replace(" km", "").replace(",", "").strip())
                    except Exception:
                        pass

            steps.append(SourcedStep(
                step_number=step_num,
                action=f"Visit {facility['name']}",
                detail=detail,
                source_url=source_url,
                source_label=facility["name"],
                agent=self.name,
                distance_km=distance_km,
            ))
            step_num += 1

        # Step 6: Add Maps-discovered nearby hospitals not already in Firestore
        firestore_names = {f["name"].lower() for f in facilities}
        for mh in maps_hospitals:
            if mh["name"].lower() not in firestore_names and step_num <= 6:
                dist_km = mh.get("distance_km")  # real distance, computed locally in maps_tool
                steps.append(SourcedStep(
                    step_number=step_num,
                    action=f"Visit {mh['name']} (nearby)",
                    detail=(
                        f"Address: {mh['address']}. "
                        f"Rating: {mh.get('rating', 'N/A')}/5 ({mh.get('user_ratings_total', 0)} reviews)."
                        + (f" | {dist_km} km away" if dist_km is not None else "")
                    ),
                    source_url=mh["maps_url"],
                    source_label=f"{mh['name']} on Google Maps",
                    agent=self.name,
                    distance_km=dist_km,
                ))
                step_num += 1

        # Sort by distance (nearest first), nulls last
        steps.sort(key=lambda s: (s.distance_km is None, s.distance_km or 0))

        # Re-number after sort
        for i, s in enumerate(steps, 1):
            s.step_number = i

        self.logger.info(f"FacilityAgent produced {len(steps)} steps")
        return AgentResult(agent_name=self.name, steps=steps, raw_data=facilities)

    async def _find_places(self, category: dict, coordinates, text_location: str, derived_city: str) -> AgentResult:
        """Places-only search for gyms, parks, pools, playgrounds, sports facilities."""
        if coordinates and coordinates.get("lat") and coordinates.get("lng"):
            loc_str = f"{coordinates['lat']},{coordinates['lng']}"
        else:
            loc_str = text_location or derived_city

        if not loc_str:
            self.logger.warning("No usable location for place search")
            return AgentResult(agent_name=self.name, steps=[], raw_data=[])

        places = await find_nearby_places(
            loc_str, keyword=category["keyword"], place_type=category["type"], max_results=6,
        )

        steps = []
        for i, p in enumerate(places, 1):
            dist = p.get("distance_km")
            detail = f"Address: {p['address']}."
            if p.get("rating"):
                detail += f" Rating: {p['rating']}/5 ({p.get('user_ratings_total', 0)} reviews)."
            if dist is not None:
                detail += f" | {dist} km away"
            steps.append(SourcedStep(
                step_number=i,
                action=f"Visit {p['name']}",
                detail=detail,
                source_url=p["maps_url"],
                source_label=f"{p['name']} on Google Maps",
                agent=self.name,
                distance_km=dist,
            ))

        steps.sort(key=lambda s: (s.distance_km is None, s.distance_km or 0))
        for i, s in enumerate(steps, 1):
            s.step_number = i

        self.logger.info(f"FacilityAgent produced {len(steps)} {category['label']} results")
        return AgentResult(agent_name=self.name, steps=steps, raw_data=places)

    _city_cache: dict[str, str] = {}

    async def _city_for_coords(self, coordinates: dict) -> str:
        """Reverse-geocode coords -> city, cached by rounded lat/lng for the process."""
        lat, lng = coordinates["lat"], coordinates["lng"]
        key = f"{round(lat, 3)},{round(lng, 3)}"
        if key in self._city_cache:
            return self._city_cache[key]
        try:
            city = await reverse_geocode(lat, lng) or ""
        except Exception as e:
            self.logger.warning(f"reverse_geocode failed: {e}")
            city = ""
        self._city_cache[key] = city
        return city

    async def _condition_to_specialty(self, condition: str) -> str:
        """Map a condition/procedure to a medical specialty."""
        mapping = {
            "eye": "ophthalmology", "vision": "ophthalmology", "cataract": "ophthalmology", "lasik": "ophthalmology",
            "heart": "cardiology", "cardiac": "cardiology",
            "cancer": "oncology", "tumor": "oncology",
            "brain": "neurology", "neuro": "neurology", "epilepsy": "neurology",
            "kidney": "nephrology", "renal": "nephrology",
            "diabetes": "endocrinology", "thyroid": "endocrinology",
            "bone": "orthopedics", "joint": "orthopedics", "knee": "orthopedics", "spine": "orthopedics",
            "mental": "psychiatry", "depression": "psychiatry", "anxiety": "psychiatry",
            "skin": "dermatology", "dental": "dentistry", "teeth": "dentistry",
            "child": "pediatrics", "baby": "pediatrics",
            "women": "gynecology", "pregnancy": "gynecology",
        }
        cond_lower = condition.lower()
        for keyword, specialty in mapping.items():
            if keyword in cond_lower:
                return specialty
        return "general_medicine"

    async def _extract_context(self, message: str, location: str) -> dict:
        system = (
            "You extract healthcare facility search parameters from a user's message. "
            "Identify the medical specialty needed, city, state, and any government scheme mentioned. "
            "Use standard Indian city names. Map conditions to specialties: "
            "cancer→oncology, heart→cardiology, brain/epilepsy→neurology, mental health→psychiatry, kidney→nephrology."
        )
        prompt = f"User message: {message}\nHint — user location: {location or 'not specified'}"
        try:
            return await self.generate_structured(system, prompt, FACILITY_CONTEXT_SCHEMA)
        except Exception as e:
            self.logger.warning(f"Context extraction failed, using defaults: {e}")
            return {"specialty_needed": "", "city": location or "", "state": "", "preferred_scheme": ""}

    async def _rank_facilities(self, facilities: list[dict], user_message: str, specialty: str) -> list[dict]:
        summaries = "\n".join(
            f"- id: {f['id']}, name: {f['name']}, city: {f['city']}, "
            f"specialties: {', '.join(f.get('specialties', [])[:4])}, "
            f"accepts_pmjay: {f.get('accepts_pmjay', False)}"
            for f in facilities
        )
        system = (
            "You are a healthcare facility advisor for India. "
            "Rank the top 3 most relevant hospitals for the user's need. "
            "Explain why each is recommended and what the user should do next. "
            "Return only facilities from the provided list using their exact IDs."
        )
        prompt = f"User need: {user_message}\nSpecialty needed: {specialty}\n\nAvailable facilities:\n{summaries}"
        try:
            return await self.generate_structured(system, prompt, RANK_SCHEMA)
        except Exception as e:
            self.logger.warning(f"Facility ranking failed, returning unranked: {e}")
            return [
                {"facility_id": f["id"], "why_recommended": f"Located in {f['city']}", "what_to_do": f"Call {f.get('phone', 'hospital')} to book appointment"}
                for f in facilities[:3]
            ]
