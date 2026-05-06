from engine.environment import Environment


def interrupted_proc(env):
    try:
        print(f"[{env.now}] interrupted_proc start")
        # wait longer but expect an interrupt
        yield env.timeout(5)
        print(f"[{env.now}] interrupted_proc finished normally")
    except Exception as e:
        print(f"[{env.now}] interrupted_proc caught {type(e).__name__}: {e}")


def interrupter(env, target_proc):
    yield env.timeout(1)
    print(f"[{env.now}] interrupter sending interrupt")
    target_proc.interrupt()


def main():
    env = Environment()
    p = env.process(lambda: interrupted_proc(env))
    env.process(lambda: interrupter(env, p))
    env.run()


if __name__ == "__main__":
    main()
