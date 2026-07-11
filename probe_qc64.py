import sys, builtins
sys.path.insert(0, "C:/æ/hermes-fork")
import qc64_basic as q

vm = q.BasicVM(q.PROGRAM)
vm.routes = [p for p, _ in q._DISPATCHER._handlers]
vm._helpers = {
    "count_routes": lambda: len(vm.routes),
    "get_routes": lambda: "",
    "route_at$": lambda i: vm.routes[i - 1] if 0 < i <= len(vm.routes) else "",
}

orig_set = vm._arr_set
def traced_set(name, idx, val):
    if name.rstrip("$") == "prefix":
        print(f"  _arr_set prefix[{idx}] = {val!r}")
    return orig_set(name, idx, val)
vm._arr_set = traced_set

feeds = iter(["viewport://hermes-agent", "exit"])
def fake_input(prompt=""):
    try:
        v = next(feeds)
    except StopIteration:
        v = "exit"
    sys.stdout.write(prompt + v + "\n")
    return v
builtins.input = fake_input

vm.run()
print("FINAL arr prefix size:", len(vm.arr.get("prefix", {})))
print("best$:", vm.vars.get("best$"), "bp:", vm.vars.get("bp"))
