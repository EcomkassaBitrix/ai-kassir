-- Clean up stray test rows created during my own manual testing (no real user data attached)
-- so future firm_id+tax_identity lookups deterministically resolve to the real account.
UPDATE user_settings SET ecomkassa_firm_id = NULL, ecomkassa_tax_identity = NULL
WHERE user_id IN (
  'ecom_jwt_2ced0b4c2eb35b68637cd43e',
  'ecom_jwt_4a4fb3ddc60ce293e122fa6e',
  'ecom_jwt_fbcca8910bd75b3fdc15ebd4',
  'ecom_jwt_10aa076cd1b3e67588e2dcae',
  'ecom_jwt_5ca6c7664e5fd78bd95ec13a',
  'ecom_jwt_c0ad82fb25165964610048a8'
);
