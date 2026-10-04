package com.schwab.urlshortener;

import static org.assertj.core.api.Assertions.assertThat;

import com.schwab.urlshortener.domain.SecureShortCodeGenerator;
import java.util.HashSet;
import java.util.Set;
import org.junit.jupiter.api.Test;

class ShortCodeGeneratorTest {
    @Test
    void generatesSevenCharacterBase62CodesWithVariation() {
        SecureShortCodeGenerator generator = new SecureShortCodeGenerator();
        Set<String> values = new HashSet<>();
        for (int i = 0; i < 100; i++) {
            String code = generator.generate();
            assertThat(code).matches("[0-9A-Za-z]{7}");
            values.add(code);
        }
        assertThat(values).hasSizeGreaterThan(1);
    }
}
