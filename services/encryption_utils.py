"""
Encryption utilities for sensitive data
Utiliza Fernet (symmetric encryption) para cifrar/descifrar datos sensibles
"""

import os
import logging
from cryptography.fernet import Fernet
from typing import Optional

logger = logging.getLogger(__name__)


class EncryptionService:
    """Servicio de cifrado/descifrado de datos sensibles"""

    def __init__(self):
        encryption_key = os.getenv("ENCRYPTION_KEY")

        if not encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY not found in environment variables. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )

        try:
            self.cipher = Fernet(encryption_key.encode())
            logger.info("✅ Encryption service initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize encryption: {e}")
            raise

    def encrypt(self, plaintext: str) -> str:
        """
        Cifra un string en texto plano

        Args:
            plaintext: Texto a cifrar

        Returns:
            Texto cifrado (base64 encoded)
        """
        if not plaintext:
            return plaintext

        try:
            encrypted_bytes = self.cipher.encrypt(plaintext.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            logger.error(f"❌ Encryption failed: {e}")
            raise

    def decrypt(self, ciphertext: str) -> str:
        """
        Descifra un string cifrado

        Args:
            ciphertext: Texto cifrado

        Returns:
            Texto en claro
        """
        if not ciphertext:
            return ciphertext

        try:
            decrypted_bytes = self.cipher.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            logger.error(f"❌ Decryption failed: {e}")
            raise

    def encrypt_dict(self, data: dict) -> dict:
        """
        Cifra valores sensibles en un diccionario

        Args:
            data: Diccionario con datos a cifrar

        Returns:
            Diccionario con valores cifrados
        """
        encrypted_data = {}

        for key, value in data.items():
            if value is None:
                encrypted_data[key] = None
            elif isinstance(value, str):
                encrypted_data[key] = self.encrypt(value)
            elif isinstance(value, list):
                # Para scopes que es una lista
                encrypted_data[key] = value
            else:
                encrypted_data[key] = value

        return encrypted_data

    def decrypt_dict(self, encrypted_data: dict) -> dict:
        """
        Descifra valores de un diccionario

        Args:
            encrypted_data: Diccionario con valores cifrados

        Returns:
            Diccionario con valores descifrados
        """
        decrypted_data = {}

        for key, value in encrypted_data.items():
            if value is None:
                decrypted_data[key] = None
            elif isinstance(value, str) and key != 'scopes':
                # No descifrar scopes (es una lista de strings)
                try:
                    decrypted_data[key] = self.decrypt(value)
                except Exception:
                    # Si falla el descifrado, probablemente no estaba cifrado
                    decrypted_data[key] = value
            else:
                decrypted_data[key] = value

        return decrypted_data


# Instancia global
encryption_service = EncryptionService()
