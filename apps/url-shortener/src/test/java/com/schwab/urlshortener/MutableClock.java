package com.schwab.urlshortener;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.concurrent.atomic.AtomicReference;

class MutableClock extends Clock {
    private final AtomicReference<Instant> now;

    MutableClock(Instant initial) {
        now = new AtomicReference<>(initial);
    }

    void set(Instant instant) {
        now.set(instant);
    }

    @Override
    public ZoneId getZone() {
        return ZoneOffset.UTC;
    }

    @Override
    public Clock withZone(ZoneId zone) {
        if (!ZoneOffset.UTC.equals(zone)) {
            throw new IllegalArgumentException("Test clock is UTC only");
        }
        return this;
    }

    @Override
    public Instant instant() {
        return now.get();
    }
}
