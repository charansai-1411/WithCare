// Location: persisted manual override > browser GPS > null.
// A manually set city (no coords) still works — the backend resolves "near me" from it.

const STORE_KEY = 'withcare_location';

export function getStoredLocation() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredLocation(loc) {
  // loc: { city, lat, lng } — lat/lng may be null for a manually typed city
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(loc));
  } catch {
    /* ignore */
  }
  return loc;
}

export async function getLocation() {
  // 1. A previously stored/typed location wins — reliable across reloads.
  const stored = getStoredLocation();
  if (stored && stored.city) return stored;

  // 2. Try browser GPS (may be denied or OS-disabled).
  const gps = await tryGps();
  if (gps) return setStoredLocation(gps);

  return null;
}

function tryGps() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve(null);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        const city = await reverseGeocode(lat, lng);
        resolve({ city, lat, lng });
      },
      () => resolve(null),
      { timeout: 8000, maximumAge: 300000, enableHighAccuracy: false }
    );
  });
}

async function reverseGeocode(lat, lng) {
  try {
    const r = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`,
      { headers: { 'Accept-Language': 'en' } }
    );
    const data = await r.json();
    return (
      data?.address?.city ||
      data?.address?.town ||
      data?.address?.county ||
      data?.address?.state ||
      'India'
    );
  } catch {
    return 'India';
  }
}
