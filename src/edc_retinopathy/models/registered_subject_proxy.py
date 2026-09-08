from edc_registration.models import RegisteredSubject


class RegisteredSubjectProxy(RegisteredSubject):
    def __str__(self):
        return f"{self.subject_identifier} {self.initials} {self.dob.strftime('%Y-%m-%d')}"

    class Meta:
        proxy = True
