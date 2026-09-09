CREATE TYPE management.blackwall_punishment AS ENUM (
    'log',
    'kick'
    'ban',
);

ALTER TABLE management.blackwall
    ADD COLUMN punishment management.blackwall_punishment NOT NULL DEFAULT 'ban';
