package com.schwab.urlshortener.application;

public class LinkNotFoundException extends RuntimeException {
    public LinkNotFoundException() {
        super("Short code not found");
    }
}
