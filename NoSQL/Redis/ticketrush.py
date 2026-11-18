
import time
import uuid
import random
from concurrent.futures import ThreadPoolExecutor

import redis


# ============================================================
# STEP 0: REDIS CONNECTION
# ============================================================

r = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)


def race(fn, n=50):
    """Run fn(i) from n threads at once."""
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(fn, range(n)))


# ============================================================
# STEP 1: SEAT HOLDS AND RACE CONDITION
# ============================================================

def hold_naive(event, seat, user):
    """Naive implementation: check then write."""

    key = f"hold:{event}:{seat}"

    if r.get(key) is None:
        time.sleep(0.01)
        r.set(key, user, ex=300)
        return True

    return False


def hold_nx(event, seat, user, ttl=300):
    """Atomic seat hold using SET NX EX."""

    return bool(
        r.set(
            f"hold:{event}:{seat}",
            user,
            nx=True,
            ex=ttl
        )
    )


# ============================================================
# STEP 2: ATOMIC HOLD, CONFIRM AND RELEASE
# ============================================================

HOLD = r.register_script("""
if redis.call('SISMEMBER', KEYS[2], ARGV[2]) == 1 then
    return 0
end

if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[3]) then
    return 1
end

return 0
""")


CONFIRM = r.register_script("""
if redis.call('GET', KEYS[1]) == ARGV[1] then
    redis.call('SADD', KEYS[2], ARGV[2])
    redis.call('DEL', KEYS[1])
    return 1
end

return 0
""")


RELEASE = r.register_script("""
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end

return 0
""")


def hold(event, seat, user, ttl=300):
    """Hold a seat if it is not sold or held."""

    return bool(
        HOLD(
            keys=[
                f"hold:{event}:{seat}",
                f"sold:{event}"
            ],
            args=[user, seat, ttl]
        )
    )


def confirm(event, seat, user):
    """Confirm a seat if the user owns the hold."""

    return bool(
        CONFIRM(
            keys=[
                f"hold:{event}:{seat}",
                f"sold:{event}"
            ],
            args=[user, seat]
        )
    )


def release(event, seat, user):
    """Release a seat only if the user owns the hold."""

    return bool(
        RELEASE(
            keys=[f"hold:{event}:{seat}"],
            args=[user]
        )
    )


def seat_map(event, seats):
    """Return the current status of each seat."""

    sold = r.smembers(f"sold:{event}")

    return {
        seat: (
            "sold" if seat in sold
            else "held" if r.exists(f"hold:{event}:{seat}")
            else "free"
        )
        for seat in seats
    }


# ============================================================
# STEP 3: FLASH SALE - GENERAL ADMISSION
# ============================================================

def buy_general(event, user):
    """Buy one general admission ticket atomically."""

    left = r.decr(f"stock:{event}")

    if left < 0:
        r.incr(f"stock:{event}")
        return False

    r.sadd(f"buyers:{event}", user)

    return True


# ============================================================
# STEP 4: RATE LIMITING
# ============================================================

def allow_fixed(user, limit=5, window=10):
    """Fixed-window rate limiter."""

    key = f"rl:fixed:{user}:{int(time.time() // window)}"

    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, window, nx=True)

    count, _ = pipe.execute()

    return count <= limit


SLIDING = r.register_script("""
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

redis.call(
    'ZREMRANGEBYSCORE',
    KEYS[1],
    0,
    now - window
)

if redis.call('ZCARD', KEYS[1]) < limit then
    redis.call('ZADD', KEYS[1], now, ARGV[4])
    redis.call('PEXPIRE', KEYS[1], window)
    return 1
end

return 0
""")


def allow_sliding(user, limit=5, window_ms=10_000):
    """Sliding-window rate limiter."""

    now = int(time.time() * 1000)

    return bool(
        SLIDING(
            keys=[f"rl:sliding:{user}"],
            args=[
                now,
                window_ms,
                limit,
                uuid.uuid4().hex
            ]
        )
    )


def try_hold(event, seat, user):
    """Rate-limit a user's seat-hold request."""

    if not allow_sliding(user):
        return "rate_limited"

    return "ok" if hold(event, seat, user) else "taken"


# ============================================================
# STEP 5: VIRTUAL WAITING ROOM
# ============================================================

def join_queue(event, user):
    """Join the waiting queue and return position."""

    r.zadd(
        f"queue:{event}",
        {user: time.time()},
        nx=True
    )

    position = r.zrank(f"queue:{event}", user)

    return position + 1


def admit(event, n):
    """Admit the first n users from the queue."""

    return [
        user
        for user, _ in r.zpopmin(f"queue:{event}", n)
    ]


# ============================================================
# STEP 6: FINAL STRESS TEST
# ============================================================

def buyer(i):
    """Each buyer tries to book the first available seat."""

    user = f"user{i}"

    for seat in SEATS:

        if hold("c1", seat, user):

            time.sleep(random.random() * 0.05)

            if confirm("c1", seat, user):
                return seat

    return None


def final_stress_test():
    """100 users compete for 20 seats."""

    r.flushdb()

    results = race(buyer, n=100)

    got = [seat for seat in results if seat]

    sold_count = r.scard("sold:c1")

    print("Tickets sold:", len(got))
    print("Distinct seats:", len(set(got)))
    print("Redis sold set:", sold_count)

    return (
        len(got),
        len(set(got)),
        sold_count
    )


SEATS = [f"S{i}" for i in range(1, 21)]


# ============================================================
# MAIN: RUN EXPERIMENTS
# ============================================================

def main():

    print("\n========== STEP 1: RACE CONDITION ==========")

    r.flushdb()

    wins = race(
        lambda i: hold_naive("c1", "A1", f"user{i}")
    )

    print("Naive winners:", sum(wins))

    r.flushdb()

    wins = race(
        lambda i: hold_nx("c1", "A1", f"user{i}")
    )

    print("SET NX winners:", sum(wins))

    print("\n========== STEP 2: SEAT BOOKING ==========")

    r.flushdb()

    print("Hold by linh:", hold("c1", "A1", "linh"))
    print("Hold by nam:", hold("c1", "A1", "nam"))
    print("Nam confirms:", confirm("c1", "A1", "nam"))
    print("Linh confirms:", confirm("c1", "A1", "linh"))
    print("Nam tries again:", hold("c1", "A1", "nam"))

    print("Seat map:", seat_map("c1", ["A1", "A2"]))

    print("\n========== STEP 3: FLASH SALE ==========")

    r.flushdb()

    r.set("stock:g1", 100)

    ok = race(
        lambda i: buy_general("g1", f"user{i}"),
        n=500
    )

    print("Successful purchases:", sum(ok))
    print("Remaining stock:", r.get("stock:g1"))
    print("Buyers:", r.scard("buyers:g1"))

    print("\n========== STEP 4: RATE LIMITING ==========")

    r.flushdb()

    print("Fixed window:", [
        allow_fixed("linh") for _ in range(8)
    ])

    r.flushdb()

    print("Sliding window:", [
        allow_sliding("linh") for _ in range(8)
    ])

    print("\n========== STEP 5: WAITING ROOM ==========")

    r.flushdb()

    for name in ["u1", "u2", "u3"]:
        print(name, join_queue("c1", name))

    print("Rejoin u1:", join_queue("c1", "u1"))
    print("Admitted:", admit("c1", 2))
    print("Rejoin u3:", join_queue("c1", "u3"))

    print("\n========== STEP 6: FINAL STRESS TEST ==========")

    result = final_stress_test()

    if result == (20, 20, 20):
        print("PASS: Final stress test")
    else:
        print("FAIL: Final stress test")


if __name__ == "__main__":
    try:
        main()

    except redis.exceptions.RedisError as e:
        print("Redis error:", e)

    finally:
        r.close()
