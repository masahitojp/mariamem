"""Native-client diagnostics adapter; library parsing lives in the installed SDK."""
class ImportFailure(RuntimeError):
    def __init__(self, reason, *, stage, location, errno=None, sqlstate=None):
        self.details = dict(reason=reason, stage=stage, location=location, errno=errno, sqlstate=sqlstate)
        super().__init__(f'{stage}: {reason}; original file location {location}')
