-- Runs once, on first start of an empty volume.
-- A separate database for automated tests, so pytest never touches development data.
CREATE DATABASE tindawise_test OWNER tindawise;
