package com.schwab.urlshortener.domain;

import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

@Component
public class AliasValidator {
    private static final Pattern FORMAT = Pattern.compile("[A-Za-z0-9_-]{3,32}");
    private static final Set<String> RESERVED =
            Set.of("api", "actuator", "swagger-ui", "v3", "health");

    public String validate(String alias) {
        if (alias == null) {
            return null;
        }
        if (!FORMAT.matcher(alias).matches() || RESERVED.contains(alias.toLowerCase(Locale.ROOT))) {
            throw new InvalidAliasException(
                    "Alias must be 3–32 letters, numbers, hyphens or underscores and must not be reserved");
        }
        return alias;
    }
}
