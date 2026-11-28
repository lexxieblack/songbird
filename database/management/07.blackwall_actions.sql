ALTER TYPE management.log_action ADD VALUE 'blackwall_log' BEFORE 'blackwall_ban';
ALTER TYPE management.log_action ADD VALUE 'blackwall_warn' BEFORE 'blackwall_ban';
ALTER TYPE management.log_action ADD VALUE 'blackwall_kick' BEFORE 'blackwall_ban';
