package com.schwab.urlshortener.application;

public class InvalidExpiryException extends RuntimeException {
    public InvalidExpiryException() {
        super("expiresAt must be in the future");
    }
}
