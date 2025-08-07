# core/enclave.py
import socket
from aegis_toolkit.config import settings

def get_attestation_document():
    enclave_socket = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    enclave_socket.connect((16, 1234))
    enclave_socket.send(b'{"get": "attestation"}')
    attestation_doc = enclave_socket.recv(4096)
    return attestation_doc

def verify_enclave_health():
    """On startup, verify we are actually inside a secure enclave."""
    config = settings.secure_enclave
    if config.provider != 'none' and config.require_attestation:
        try:
            doc = get_attestation_document()
            print("SUCCESS: Attestation document received. Running in a secure enclave.")
        except Exception as e:
            print(f"FATAL: Could not get attestation document. Not a secure environment. {e}")
            exit(1) # Fail closed
    else:
        print("INFO: Enclave verification is disabled in config.yaml.")