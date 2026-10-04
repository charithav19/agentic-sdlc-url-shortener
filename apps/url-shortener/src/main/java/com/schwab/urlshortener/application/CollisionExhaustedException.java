package com.schwab.urlshortener.application;

public class CollisionExhaustedException extends RuntimeException {
    public CollisionExhaustedException() {
        super("Could not allocate a unique short code after five attempts");
    }
}
