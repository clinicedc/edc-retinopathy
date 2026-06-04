from .autocomplete_admin import RegisteredSubjectProxyAdmin
from .camera_session_admin import CameraSessionAdmin
from .contact_attempt_admin import ContactAttemptAdmin
from .dm_retinopathy_screening_admin import DmRetinopathyScreeningAdmin
from .referral_followup_admin import ReferralFollowupAdmin
from .session_file_admin import SessionFileAdmin

__all__ = [
    "CameraSessionAdmin",
    "ContactAttemptAdmin",
    "DmRetinopathyScreeningAdmin",
    "ReferralFollowupAdmin",
    "RegisteredSubjectProxyAdmin",
    "SessionFileAdmin",
]
