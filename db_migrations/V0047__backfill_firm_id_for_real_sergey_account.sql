-- Consolidate stray test accounts back into the real sergey@ecomkassa.ru account that
-- were created earlier by the now-fixed unstable jwt "sub" logic.
UPDATE user_settings SET ecomkassa_firm_id = '9fd3f105-1b8a-42d9-8497-55d25edf0fb0', ecomkassa_tax_identity = '7724923302'
WHERE user_id = 'ecom_sergey@ecomkassa.ru';
