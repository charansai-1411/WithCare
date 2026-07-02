class WithCareError(Exception):
    pass


class ClinicalRequestError(WithCareError):
    message = (
        "WithCare does not provide clinical advice, diagnoses, or treatment recommendations. "
        "Please consult a licensed healthcare professional for medical guidance."
    )

    def __init__(self):
        super().__init__(self.message)


class AgentRoutingError(WithCareError):
    pass


class FirestoreError(WithCareError):
    pass


class GroundingError(WithCareError):
    pass


class CalendarActionError(WithCareError):
    pass


class GeminiServiceError(WithCareError):
    pass
