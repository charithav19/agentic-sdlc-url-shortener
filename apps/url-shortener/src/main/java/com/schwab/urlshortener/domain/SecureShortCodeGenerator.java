package com.schwab.urlshortener.domain;

import java.security.SecureRandom;
import org.springframework.stereotype.Component;

@Component
public class SecureShortCodeGenerator implements ShortCodeGenerator {
    private static final char[] ALPHABET =
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz".toCharArray();
    private static final int CODE_LENGTH = 7;

    private final SecureRandom random = new SecureRandom();

    @Override
    public String generate() {
        char[] code = new char[CODE_LENGTH];
        for (int i = 0; i < code.length; i++) {
            code[i] = ALPHABET[random.nextInt(ALPHABET.length)];
        }
        return new String(code);
    }
}
