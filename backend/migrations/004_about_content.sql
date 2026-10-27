-- Extend the existing profile; retain all administrator accounts and profile fields.
ALTER TABLE site_profile ADD COLUMN about_content jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(about_content) = 'object');
