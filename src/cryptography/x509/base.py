# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import abc
import datetime
import os
import typing
from enum import Enum

from cryptography.hazmat._types import _PRIVATE_KEY_TYPES, _PUBLIC_KEY_TYPES
from cryptography.hazmat.backends import _get_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import (
    dsa,
    ec,
    ed25519,
    ed448,
    rsa,
)
from cryptography.x509.extensions import Extension, ExtensionType, Extensions
from cryptography.x509.name import Name
from cryptography.x509.oid import ObjectIdentifier


_EARLIEST_UTC_TIME = datetime.datetime(1950, 1, 1)


class AttributeNotFound(Exception):
    def __init__(self, msg, oid):
        super(AttributeNotFound, self).__init__(msg)
        self.oid = oid


class CheckIssuedFail(Exception):
    def __init__(self, msg, err_code):
        super(CheckIssuedFail, self).__init__(msg, err_code)


def _reject_duplicate_extension(
    extension: Extension, extensions: typing.List[Extension]
):
    # This is quadratic in the number of extensions
    for e in extensions:
        if e.oid == extension.oid:
            raise ValueError("This extension has already been set.")


def _reject_duplicate_attribute(
    oid: ObjectIdentifier,
    attributes: typing.List[typing.Tuple[ObjectIdentifier, bytes]],
):
    # This is quadratic in the number of attributes
    for attr_oid, _ in attributes:
        if attr_oid == oid:
            raise ValueError("This attribute has already been set.")


def _convert_to_naive_utc_time(time: datetime.datetime) -> datetime.datetime:
    """Normalizes a datetime to a naive datetime in UTC.

    time -- datetime to normalize. Assumed to be in UTC if not timezone
            aware.
    """
    if time.tzinfo is not None:
        offset = time.utcoffset()
        offset = offset if offset else datetime.timedelta()
        return time.replace(tzinfo=None) - offset
    else:
        return time


class Version(Enum):
    v1 = 0
    v3 = 2


class InvalidVersion(Exception):
    def __init__(self, msg, parsed_version):
        super(InvalidVersion, self).__init__(msg)
        self.parsed_version = parsed_version


class Certificate(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def fingerprint(self, algorithm: hashes.HashAlgorithm) -> bytes:
        """
        Returns bytes using digest passed.
        """

    @abc.abstractproperty
    def serial_number(self) -> int:
        """
        Returns certificate serial number
        """

    @abc.abstractproperty
    def version(self) -> Version:
        """
        Returns the certificate version
        """

    @abc.abstractmethod
    def public_key(self) -> _PUBLIC_KEY_TYPES:
        """
        Returns the public key
        """

    @abc.abstractproperty
    def not_valid_before(self) -> datetime.datetime:
        """
        Not before time (represented as UTC datetime)
        """

    @abc.abstractproperty
    def not_valid_after(self) -> datetime.datetime:
        """
        Not after time (represented as UTC datetime)
        """

    @abc.abstractproperty
    def issuer(self) -> Name:
        """
        Returns the issuer name object.
        """

    @abc.abstractproperty
    def subject(self) -> Name:
        """
        Returns the subject name object.
        """

    @abc.abstractproperty
    def signature_hash_algorithm(
        self,
    ) -> typing.Optional[hashes.HashAlgorithm]:
        """
        Returns a HashAlgorithm corresponding to the type of the digest signed
        in the certificate.
        """

    @abc.abstractproperty
    def signature_algorithm_oid(self) -> ObjectIdentifier:
        """
        Returns the ObjectIdentifier of the signature algorithm.
        """

    @abc.abstractproperty
    def extensions(self) -> Extensions:
        """
        Returns an Extensions object.
        """

    @abc.abstractproperty
    def signature(self) -> bytes:
        """
        Returns the signature bytes.
        """

    @abc.abstractproperty
    def tbs_certificate_bytes(self) -> bytes:
        """
        Returns the tbsCertificate payload bytes as defined in RFC 5280.
        """

    @abc.abstractmethod
    def __eq__(self, other: object) -> bool:
        """
        Checks equality.
        """

    @abc.abstractmethod
    def __ne__(self, other: object) -> bool:
        """
        Checks not equal.
        """

    @abc.abstractmethod
    def __hash__(self) -> int:
        """
        Computes a hash.
        """

    @abc.abstractmethod
    def public_bytes(self, encoding: serialization.Encoding) -> bytes:
        """
        Serializes the certificate to PEM or DER format.
        """

    @abc.abstractmethod
    def check_issued(self, issuer):
        """
        Verifies that the certificate was issued by the given issuer.
        """


class RevokedCertificate(metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def serial_number(self) -> int:
        """
        Returns the serial number of the revoked certificate.
        """

    @abc.abstractproperty
    def revocation_date(self) -> datetime.datetime:
        """
        Returns the date of when this certificate was revoked.
        """

    @abc.abstractproperty
    def extensions(self) -> Extensions:
        """
        Returns an Extensions object containing a list of Revoked extensions.
        """


class CertificateRevocationList(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def public_bytes(self, encoding: serialization.Encoding) -> bytes:
        """
        Serializes the CRL to PEM or DER format.
        """

    @abc.abstractmethod
    def fingerprint(self, algorithm: hashes.HashAlgorithm) -> bytes:
        """
        Returns bytes using digest passed.
        """

    @abc.abstractmethod
    def get_revoked_certificate_by_serial_number(
        self, serial_number: int
    ) -> typing.Optional[RevokedCertificate]:
        """
        Returns an instance of RevokedCertificate or None if the serial_number
        is not in the CRL.
        """

    @abc.abstractproperty
    def signature_hash_algorithm(self) -> hashes.HashAlgorithm:
        """
        Returns a HashAlgorithm corresponding to the type of the digest signed
        in the certificate.
        """

    @abc.abstractproperty
    def signature_algorithm_oid(self) -> ObjectIdentifier:
        """
        Returns the ObjectIdentifier of the signature algorithm.
        """

    @abc.abstractproperty
    def issuer(self) -> Name:
        """
        Returns the X509Name with the issuer of this CRL.
        """

    @abc.abstractproperty
    def next_update(self) -> datetime.datetime:
        """
        Returns the date of next update for this CRL.
        """

    @abc.abstractproperty
    def last_update(self) -> datetime.datetime:
        """
        Returns the date of last update for this CRL.
        """

    @abc.abstractproperty
    def extensions(self) -> Extensions:
        """
        Returns an Extensions object containing a list of CRL extensions.
        """

    @abc.abstractproperty
    def signature(self) -> bytes:
        """
        Returns the signature bytes.
        """

    @abc.abstractproperty
    def tbs_certlist_bytes(self) -> bytes:
        """
        Returns the tbsCertList payload bytes as defined in RFC 5280.
        """

    @abc.abstractmethod
    def __eq__(self, other: object) -> bool:
        """
        Checks equality.
        """

    @abc.abstractmethod
    def __ne__(self, other: object) -> bool:
        """
        Checks not equal.
        """

    @abc.abstractmethod
    def __len__(self) -> int:
        """
        Number of revoked certificates in the CRL.
        """

    @abc.abstractmethod
    def __getitem__(self, idx):
        """
        Returns a revoked certificate (or slice of revoked certificates).
        """

    @abc.abstractmethod
    def __iter__(self):
        """
        Iterator over the revoked certificates
        """

    @abc.abstractmethod
    def is_signature_valid(self, public_key: _PUBLIC_KEY_TYPES) -> bool:
        """
        Verifies signature of revocation list against given public key.
        """


class CertificateSigningRequest(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __eq__(self, other: object) -> bool:
        """
        Checks equality.
        """

    @abc.abstractmethod
    def __ne__(self, other: object) -> bool:
        """
        Checks not equal.
        """

    @abc.abstractmethod
    def __hash__(self) -> int:
        """
        Computes a hash.
        """

    @abc.abstractmethod
    def public_key(self) -> _PUBLIC_KEY_TYPES:
        """
        Returns the public key
        """

    @abc.abstractproperty
    def subject(self) -> Name:
        """
        Returns the subject name object.
        """

    @abc.abstractproperty
    def signature_hash_algorithm(self) -> hashes.HashAlgorithm:
        """
        Returns a HashAlgorithm corresponding to the type of the digest signed
        in the certificate.
        """

    @abc.abstractproperty
    def signature_algorithm_oid(self) -> ObjectIdentifier:
        """
        Returns the ObjectIdentifier of the signature algorithm.
        """

    @abc.abstractproperty
    def extensions(self) -> Extensions:
        """
        Returns the extensions in the signing request.
        """

    @abc.abstractmethod
    def public_bytes(self, encoding: serialization.Encoding) -> bytes:
        """
        Encodes the request to PEM or DER format.
        """

    @abc.abstractproperty
    def signature(self) -> bytes:
        """
        Returns the signature bytes.
        """

    @abc.abstractproperty
    def tbs_certrequest_bytes(self) -> bytes:
        """
        Returns the PKCS#10 CertificationRequestInfo bytes as defined in RFC
        2986.
        """

    @abc.abstractproperty
    def is_signature_valid(self) -> bool:
        """
        Verifies signature of signing request.
        """

    @abc.abstractmethod
    def get_attribute_for_oid(self, oid: ObjectIdentifier) -> bytes:
        """
        Get the attribute value for a given OID.
        """


def load_pem_x509_certificate(data: bytes, backend=None) -> Certificate:
    backend = _get_backend(backend)
    return backend.load_pem_x509_certificate(data)


def load_der_x509_certificate(data: bytes, backend=None) -> Certificate:
    backend = _get_backend(backend)
    return backend.load_der_x509_certificate(data)


def load_pem_x509_csr(data: bytes, backend=None) -> CertificateSigningRequest:
    backend = _get_backend(backend)
    return backend.load_pem_x509_csr(data)


def load_der_x509_csr(data: bytes, backend=None) -> CertificateSigningRequest:
    backend = _get_backend(backend)
    return backend.load_der_x509_csr(data)


def load_pem_x509_crl(data: bytes, backend=None) -> CertificateRevocationList:
    backend = _get_backend(backend)
    return backend.load_pem_x509_crl(data)


def load_der_x509_crl(data: bytes, backend=None) -> CertificateRevocationList:
    backend = _get_backend(backend)
    return backend.load_der_x509_crl(data)


class CertificateSigningRequestBuilder(object):
    def __init__(self, subject_name=None, extensions=[], attributes=[]):
        """
        Creates an empty X.509 certificate request (v1).
        """
        self._subject_name = subject_name
        self._extensions = extensions
        self._attributes = attributes

    def subject_name(self, name: Name):
        """
        Sets the certificate requestor's distinguished name.
        """
        if not isinstance(name, Name):
            raise TypeError("Expecting x509.Name object.")
        if self._subject_name is not None:
            raise ValueError("The subject name may only be set once.")
        return CertificateSigningRequestBuilder(
            name, self._extensions, self._attributes
        )

    def add_extension(self, extval: ExtensionType, critical: bool):
        """
        Adds an X.509 extension to the certificate request.
        """
        if not isinstance(extval, ExtensionType):
            raise TypeError("extension must be an ExtensionType")

        extension = Extension(extval.oid, critical, extval)
        _reject_duplicate_extension(extension, self._extensions)

        return CertificateSigningRequestBuilder(
            self._subject_name,
            self._extensions + [extension],
            self._attributes,
        )

    def add_attribute(self, oid: ObjectIdentifier, value: bytes):
        """
        Adds an X.509 attribute with an OID and associated value.
        """
        if not isinstance(oid, ObjectIdentifier):
            raise TypeError("oid must be an ObjectIdentifier")

        if not isinstance(value, bytes):
            raise TypeError("value must be bytes")

        _reject_duplicate_attribute(oid, self._attributes)

        return CertificateSigningRequestBuilder(
            self._subject_name,
            self._extensions,
            self._attributes + [(oid, value)],
        )

    def sign(
        self,
        private_key: _PRIVATE_KEY_TYPES,
        algorithm: hashes.HashAlgorithm,
        backend=None,
    ) -> CertificateSigningRequest:
        """
        Signs the request using the requestor's private key.
        """
        backend = _get_backend(backend)
        if self._subject_name is None:
            raise ValueError("A CertificateSigningRequest must have a subject")
        return backend.create_x509_csr(self, private_key, algorithm)


class CertificateBuilder(object):
    def __init__(
        self,
        issuer_name=None,
        subject_name=None,
        public_key=None,
        serial_number=None,
        not_valid_before=None,
        not_valid_after=None,
        extensions=[],
    ):
        self._version = Version.v3
        self._issuer_name = issuer_name
        self._subject_name = subject_name
        self._public_key = public_key
        self._serial_number = serial_number
        self._not_valid_before = not_valid_before
        self._not_valid_after = not_valid_after
        self._extensions = extensions

    def issuer_name(self, name: Name):
        """
        Sets the CA's distinguished name.
        """
        if not isinstance(name, Name):
            raise TypeError("Expecting x509.Name object.")
        if self._issuer_name is not None:
            raise ValueError("The issuer name may only be set once.")
        return CertificateBuilder(
            name,
            self._subject_name,
            self._public_key,
            self._serial_number,
            self._not_valid_before,
            self._not_valid_after,
            self._extensions,
        )

    def subject_name(self, name: Name):
        """
        Sets the requestor's distinguished name.
        """
        if not isinstance(name, Name):
            raise TypeError("Expecting x509.Name object.")
        if self._subject_name is not None:
            raise ValueError("The subject name may only be set once.")
        return CertificateBuilder(
            self._issuer_name,
            name,
            self._public_key,
            self._serial_number,
            self._not_valid_before,
            self._not_valid_after,
            self._extensions,
        )

    def public_key(
        self,
        key: _PUBLIC_KEY_TYPES,
    ):
        """
        Sets the requestor's public key (as found in the signing request).
        """
        if not isinstance(
            key,
            (
                dsa.DSAPublicKey,
                rsa.RSAPublicKey,
                ec.EllipticCurvePublicKey,
                ed25519.Ed25519PublicKey,
                ed448.Ed448PublicKey,
            ),
        ):
            raise TypeError(
                "Expecting one of DSAPublicKey, RSAPublicKey,"
                " EllipticCurvePublicKey, Ed25519PublicKey or"
                " Ed448PublicKey."
            )
        if self._public_key is not None:
            raise ValueError("The public key may only be set once.")
        return CertificateBuilder(
            self._issuer_name,
            self._subject_name,
            key,
            self._serial_number,
            self._not_valid_before,
            self._not_valid_after,
            self._extensions,
        )

    def serial_number(self, number: int):
        """
        Sets the certificate serial number.
        """
        if not isinstance(number, int):
            raise TypeError("Serial number must be of integral type.")
        if self._serial_number is not None:
            raise ValueError("The serial number may only be set once.")
        if number <= 0:
            raise ValueError("The serial number should be positive.")

        # ASN.1 integers are always signed, so most significant bit must be
        # zero.
        if number.bit_length() >= 160:  # As defined in RFC 5280
            raise ValueError(
                "The serial number should not be more than 159 " "bits."
            )
        return CertificateBuilder(
            self._issuer_name,
            self._subject_name,
            self._public_key,
            number,
            self._not_valid_before,
            self._not_valid_after,
            self._extensions,
        )

    def not_valid_before(self, time: datetime.datetime):
        """
        Sets the certificate activation time.
        """
        if not isinstance(time, datetime.datetime):
            raise TypeError("Expecting datetime object.")
        if self._not_valid_before is not None:
            raise ValueError("The not valid before may only be set once.")
        time = _convert_to_naive_utc_time(time)
        if time < _EARLIEST_UTC_TIME:
            raise ValueError(
                "The not valid before date must be on or after"
                " 1950 January 1)."
            )
        if self._not_valid_after is not None and time > self._not_valid_after:
            raise ValueError(
                "The not valid before date must be before the not valid after "
                "date."
            )
        return CertificateBuilder(
            self._issuer_name,
            self._subject_name,
            self._public_key,
            self._serial_number,
            time,
            self._not_valid_after,
            self._extensions,
        )

    def not_valid_after(self, time: datetime.datetime):
        """
        Sets the certificate expiration time.
        """
        if not isinstance(time, datetime.datetime):
            raise TypeError("Expecting datetime object.")
        if self._not_valid_after is not None:
            raise ValueError("The not valid after may only be set once.")
        time = _convert_to_naive_utc_time(time)
        if time < _EARLIEST_UTC_TIME:
            raise ValueError(
                "The not valid after date must be on or after"
                " 1950 January 1."
            )
        if (
            self._not_valid_before is not None
            and time < self._not_valid_before
        ):
            raise ValueError(
                "The not valid after date must be after the not valid before "
                "date."
            )
        return CertificateBuilder(
            self._issuer_name,
            self._subject_name,
            self._public_key,
            self._serial_number,
            self._not_valid_before,
            time,
            self._extensions,
        )

    def add_extension(self, extval: ExtensionType, critical: bool):
        """
        Adds an X.509 extension to the certificate.
        """
        if not isinstance(extval, ExtensionType):
            raise TypeError("extension must be an ExtensionType")

        extension = Extension(extval.oid, critical, extval)
        _reject_duplicate_extension(extension, self._extensions)

        return CertificateBuilder(
            self._issuer_name,
            self._subject_name,
            self._public_key,
            self._serial_number,
            self._not_valid_before,
            self._not_valid_after,
            self._extensions + [extension],
        )

    def sign(
        self,
        private_key: _PRIVATE_KEY_TYPES,
        algorithm: hashes.HashAlgorithm,
        backend=None,
    ) -> Certificate:
        """
        Signs the certificate using the CA's private key.
        """
        backend = _get_backend(backend)
        if self._subject_name is None:
            raise ValueError("A certificate must have a subject name")

        if self._issuer_name is None:
            raise ValueError("A certificate must have an issuer name")

        if self._serial_number is None:
            raise ValueError("A certificate must have a serial number")

        if self._not_valid_before is None:
            raise ValueError("A certificate must have a not valid before time")

        if self._not_valid_after is None:
            raise ValueError("A certificate must have a not valid after time")

        if self._public_key is None:
            raise ValueError("A certificate must have a public key")

        return backend.create_x509_certificate(self, private_key, algorithm)


class CertificateRevocationListBuilder(object):
    def __init__(
        self,
        issuer_name=None,
        last_update=None,
        next_update=None,
        extensions=[],
        revoked_certificates=[],
    ):
        self._issuer_name = issuer_name
        self._last_update = last_update
        self._next_update = next_update
        self._extensions = extensions
        self._revoked_certificates = revoked_certificates

    def issuer_name(self, issuer_name: Name):
        if not isinstance(issuer_name, Name):
            raise TypeError("Expecting x509.Name object.")
        if self._issuer_name is not None:
            raise ValueError("The issuer name may only be set once.")
        return CertificateRevocationListBuilder(
            issuer_name,
            self._last_update,
            self._next_update,
            self._extensions,
            self._revoked_certificates,
        )

    def last_update(self, last_update: datetime.datetime):
        if not isinstance(last_update, datetime.datetime):
            raise TypeError("Expecting datetime object.")
        if self._last_update is not None:
            raise ValueError("Last update may only be set once.")
        last_update = _convert_to_naive_utc_time(last_update)
        if last_update < _EARLIEST_UTC_TIME:
            raise ValueError(
                "The last update date must be on or after" " 1950 January 1."
            )
        if self._next_update is not None and last_update > self._next_update:
            raise ValueError(
                "The last update date must be before the next update date."
            )
        return CertificateRevocationListBuilder(
            self._issuer_name,
            last_update,
            self._next_update,
            self._extensions,
            self._revoked_certificates,
        )

    def next_update(self, next_update: datetime.datetime):
        if not isinstance(next_update, datetime.datetime):
            raise TypeError("Expecting datetime object.")
        if self._next_update is not None:
            raise ValueError("Last update may only be set once.")
        next_update = _convert_to_naive_utc_time(next_update)
        if next_update < _EARLIEST_UTC_TIME:
            raise ValueError(
                "The last update date must be on or after" " 1950 January 1."
            )
        if self._last_update is not None and next_update < self._last_update:
            raise ValueError(
                "The next update date must be after the last update date."
            )
        return CertificateRevocationListBuilder(
            self._issuer_name,
            self._last_update,
            next_update,
            self._extensions,
            self._revoked_certificates,
        )

    def add_extension(self, extval: ExtensionType, critical: bool):
        """
        Adds an X.509 extension to the certificate revocation list.
        """
        if not isinstance(extval, ExtensionType):
            raise TypeError("extension must be an ExtensionType")

        extension = Extension(extval.oid, critical, extval)
        _reject_duplicate_extension(extension, self._extensions)
        return CertificateRevocationListBuilder(
            self._issuer_name,
            self._last_update,
            self._next_update,
            self._extensions + [extension],
            self._revoked_certificates,
        )

    def add_revoked_certificate(self, revoked_certificate: RevokedCertificate):
        """
        Adds a revoked certificate to the CRL.
        """
        if not isinstance(revoked_certificate, RevokedCertificate):
            raise TypeError("Must be an instance of RevokedCertificate")

        return CertificateRevocationListBuilder(
            self._issuer_name,
            self._last_update,
            self._next_update,
            self._extensions,
            self._revoked_certificates + [revoked_certificate],
        )

    def sign(
        self,
        private_key: _PRIVATE_KEY_TYPES,
        algorithm: hashes.HashAlgorithm,
        backend=None,
    ) -> CertificateRevocationList:
        backend = _get_backend(backend)
        if self._issuer_name is None:
            raise ValueError("A CRL must have an issuer name")

        if self._last_update is None:
            raise ValueError("A CRL must have a last update time")

        if self._next_update is None:
            raise ValueError("A CRL must have a next update time")

        return backend.create_x509_crl(self, private_key, algorithm)


class RevokedCertificateBuilder(object):
    def __init__(
        self, serial_number=None, revocation_date=None, extensions=[]
    ):
        self._serial_number = serial_number
        self._revocation_date = revocation_date
        self._extensions = extensions

    def serial_number(self, number: int):
        if not isinstance(number, int):
            raise TypeError("Serial number must be of integral type.")
        if self._serial_number is not None:
            raise ValueError("The serial number may only be set once.")
        if number <= 0:
            raise ValueError("The serial number should be positive")

        # ASN.1 integers are always signed, so most significant bit must be
        # zero.
        if number.bit_length() >= 160:  # As defined in RFC 5280
            raise ValueError(
                "The serial number should not be more than 159 " "bits."
            )
        return RevokedCertificateBuilder(
            number, self._revocation_date, self._extensions
        )

    def revocation_date(self, time: datetime.datetime):
        if not isinstance(time, datetime.datetime):
            raise TypeError("Expecting datetime object.")
        if self._revocation_date is not None:
            raise ValueError("The revocation date may only be set once.")
        time = _convert_to_naive_utc_time(time)
        if time < _EARLIEST_UTC_TIME:
            raise ValueError(
                "The revocation date must be on or after" " 1950 January 1."
            )
        return RevokedCertificateBuilder(
            self._serial_number, time, self._extensions
        )

    def add_extension(self, extval: ExtensionType, critical: bool):
        if not isinstance(extval, ExtensionType):
            raise TypeError("extension must be an ExtensionType")

        extension = Extension(extval.oid, critical, extval)
        _reject_duplicate_extension(extension, self._extensions)
        return RevokedCertificateBuilder(
            self._serial_number,
            self._revocation_date,
            self._extensions + [extension],
        )

    def build(self, backend=None) -> RevokedCertificate:
        backend = _get_backend(backend)
        if self._serial_number is None:
            raise ValueError("A revoked certificate must have a serial number")
        if self._revocation_date is None:
            raise ValueError(
                "A revoked certificate must have a revocation date"
            )

        return backend.create_x509_revoked_certificate(self)


def random_serial_number() -> int:
    return int.from_bytes(os.urandom(20), "big") >> 1
