from edc_auth.site_auths import site_auths

from .auth_objects import (
    EDC_RETINOPATHY_ROLE,
    RETINOPATHY,
    RETINOPATHY_SUPER,
    RETINOPATHY_VIEW,
    codenames,
)

site_auths.add_group(*codenames, name=RETINOPATHY_VIEW, view_only=True)
site_auths.add_group(*codenames, name=RETINOPATHY, no_delete=True)
site_auths.add_group(*codenames, name=RETINOPATHY_SUPER)
site_auths.add_role(RETINOPATHY, name=EDC_RETINOPATHY_ROLE)
