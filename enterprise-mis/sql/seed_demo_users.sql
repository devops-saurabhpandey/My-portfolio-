USE enterprise_mis;

-- Portfolio/demo seed data only. Replace these bcrypt hashes and credentials before production use.
INSERT INTO users (username, password_hash, role)
VALUES
  ('admin', '$2b$12$REPLACE_WITH_BCRYPT_HASH', 'ADMIN'),
  ('manager', '$2b$12$REPLACE_WITH_BCRYPT_HASH', 'MANAGER'),
  ('viewer', '$2b$12$REPLACE_WITH_BCRYPT_HASH', 'VIEWER')
ON DUPLICATE KEY UPDATE role = VALUES(role);
