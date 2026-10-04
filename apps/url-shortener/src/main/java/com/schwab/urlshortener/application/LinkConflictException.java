package com.schwab.urlshortener.application;

public class LinkConflictException extends RuntimeException {
    private final String code;

    public LinkConflictException(String code, String message) {
        super(message);
        this.code = code;
    }

    public String getCode() {
        return code;
    }
}
