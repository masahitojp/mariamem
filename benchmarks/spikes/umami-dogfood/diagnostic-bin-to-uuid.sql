-- Diagnostic bootstrap for FRESH EMPTY MySQL-profile Umami installs only.
-- Not product code, not a complete MySQL BIN_TO_UUID implementation.
-- No swap_flag or invalid-input compatibility; existing-row backfill is unqualified.
CREATE FUNCTION BIN_TO_UUID(b BINARY(16)) RETURNS CHAR(36)
DETERMINISTIC NO SQL
RETURN LOWER(CONCAT(SUBSTRING(HEX(b),1,8),'-',SUBSTRING(HEX(b),9,4),'-',SUBSTRING(HEX(b),13,4),'-',SUBSTRING(HEX(b),17,4),'-',SUBSTRING(HEX(b),21,12)))
