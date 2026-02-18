-- Migration: Add Custom ASR Endpoint Configuration
-- Stores JSON config: { "endpoint": "...", "apiKey": "...", "model": "...", "language": "en" }
ALTER TABLE transcript_settings ADD COLUMN customASRConfig TEXT;
