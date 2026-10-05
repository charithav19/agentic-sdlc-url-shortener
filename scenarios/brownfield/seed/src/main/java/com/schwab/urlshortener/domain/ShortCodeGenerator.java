package com.schwab.urlshortener.domain;

import java.security.SecureRandom;
import org.springframework.stereotype.Component;

@Component
public class ShortCodeGenerator {
    private static final char[] BASE62 =
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz".toCharArray();
    private final SecureRandom random = new SecureRandom();

    public String nextCode() {
        var code = new char[7];
        for (int index = 0; index < code.length; index++) {
            code[index] = BASE62[random.nextInt(BASE62.length)];
        }
        return new String(code);
    }
}
