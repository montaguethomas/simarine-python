class ProtocolError(Exception):
  """Base class for Simarine protocol errors."""


class InvalidHeaderLength(ProtocolError):
  pass


class InvalidHeaderPrefix(ProtocolError):
  pass


class InvalidHeaderTerminator(ProtocolError):
  pass


class MessageTypeMismatch(ProtocolError):
  pass


class InvalidPayloadLength(ProtocolError):
  pass


class CRCMismatch(ProtocolError):
  pass


class TransportError(Exception):
  """Base class for Simarine transport errors."""


class TransportOpenError(TransportError):
  pass


class TransportAlreadyOpen(TransportError):
  pass


class ClientError(Exception):
  """Base class for Simarine client errors."""


class UDPListenerAlreadyRunning(ClientError):
  pass


class UDPListenerNotRunning(ClientError):
  pass
