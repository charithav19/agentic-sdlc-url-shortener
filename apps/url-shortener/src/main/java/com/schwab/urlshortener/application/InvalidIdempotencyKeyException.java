package com.schwab.urlshortener.application;

public class InvalidIdempotencyKeyException extends RuntimeException {
    public InvalidIdempotencyKeyException() {
        super("Idempotency-Key must contain 1–128 visible ASCII characters");
    }
}
