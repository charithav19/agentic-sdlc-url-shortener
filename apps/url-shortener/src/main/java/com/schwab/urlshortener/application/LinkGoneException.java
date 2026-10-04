package com.schwab.urlshortener.application;

public class LinkGoneException extends RuntimeException {
    public LinkGoneException() {
        super("Link is expired or disabled");
    }
}
