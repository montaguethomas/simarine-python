class SimarineProtocolError(Exception):
  """Base class for Simarine protocol errors."""


class InvalidHeaderLength(SimarineProtocolError):
  pass


class InvalidHeaderPrefix(SimarineProtocolError):
  pass


class InvalidHeaderTerminator(SimarineProtocolError):
  pass


class MessageTypeMismatch(SimarineProtocolError):
  pass


class InvalidPayloadLength(SimarineProtocolError):
  pass


class CRCMismatch(SimarineProtocolError):
  pass
