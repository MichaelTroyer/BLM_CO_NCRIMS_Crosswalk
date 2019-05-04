class NCRIMSError(ValueError):
    pass

class DomainError(NCRIMSError):
    pass

class FormatDataError(NCRIMSError):
    pass

class FormatDateError(NCRIMSError):
    pass

class ValueCountError(NCRIMSError):
    pass