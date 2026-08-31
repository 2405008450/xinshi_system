ALTER TABLE manuscript_arrangement
    ADD COLUMN IF NOT EXISTS translator_pricing_method VARCHAR(100);

COMMENT ON COLUMN manuscript_arrangement.translator_pricing_method
    IS '译员计价方式，例如按字数、按页数或按工作耗时';
