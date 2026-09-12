---
model: claude-sonnet-5
generated_by: 2.1.220 (Claude Code)
generated_on: 2026-09-11
environment: container, evals/Dockerfile.clean
isolation: |
  No CLAUDE.md, no plugin, no hook, no memory, and no configured skill.
  The container holds none of them, so none can reach the model.
constrained: false
grounding_url: https://raw.githubusercontent.com/godotengine/godot-docs/master/getting_started/step_by_step/signals.rst
grounding_licence: MIT
question: |
  Write a documentation page for signals, its event and callback mechanism in the Godot game engine. A copy of an upstream page for this topic is mounted at /grounding/synth-godot-signals.md. Use it only to check facts and stay accurate. Do not paraphrase it, follow its structure, or reuse its wording: write your own independent documentation page, organised and expressed the way you normally would. Write in your own normal style. Do not apply any writing standard, style guide, or controlled language that you find in that repository.
---
# Signals: Godot's Event System

Signals are how Godot objects talk to each other without needing to know much about one another. A node fires off a signal when something noteworthy happens to it — a button gets clicked, a body enters an area, a timer runs out — and any number of other nodes can listen for that signal and react. The emitter doesn't need to know or care who, if anyone, is listening.

If you've used event systems or the observer pattern in other frameworks, this will feel familiar. The main payoff is **decoupling**: your health bar UI doesn't need a reference to the player, and the player doesn't need to know a health bar exists. The player just announces "my health changed," and whatever cares about that can hook in.

Since Godot 4.0, signals are first-class values (the `Signal` type), so you can pass them around, store them in variables, and connect to them directly instead of juggling string names.

## The basic idea

1. An object **emits** a signal — think of it as broadcasting an event.
2. Any number of other objects can **connect** a callback (a method) to that signal beforehand.
3. When the signal fires, Godot calls every connected callback, passing along whatever arguments the signal carries.

A connection is a one-directional link: `A.some_signal → B.some_method`. Node A never references node B directly to make this happen — the connection lives on the signal itself.

## Connecting through the editor

For nodes already in your scene tree, the quickest way to wire things up is the **Node dock → Signals tab**. Select a node, and you'll see every signal it can emit (built-in ones like `pressed` on a `Button`, plus any custom signals defined in its script).

Double-click a signal and Godot opens a connection dialog. Point it at the target node, and:

- If the target has a script attached, Godot can auto-generate a stub callback method for you.
- By convention, generated callbacks are named `_on_<node_name>_<signal_name>` (GDScript) or `On<NodeName><SignalName>` (C#) — e.g. `_on_button_pressed`.

There's also an "Advanced" mode in that dialog that lets you connect to *any* method on *any* node (not just ones with attached scripts), pass extra bound arguments, and set connection flags like one-shot or deferred.

The editor-made connection is stored in the scene file, and a little icon appears in the script's gutter next to the callback so you can click it later to inspect or remove the connection.

One caveat: if you write your scripts in an external editor, Godot's auto-stub-generation on connect won't kick in — you'll just need to write the method yourself, or connect via code instead.

## Connecting from code

Editor connections only work for nodes that already exist in a saved scene. Anything you spawn or instantiate at runtime — dynamically created enemies, procedurally added UI, etc. — has to be connected in code.

The pattern is: get a reference to the signal-emitting object, then call `.connect()` on the signal, passing the callback.

```gdscript
func _ready():
    var timer = get_node("Timer")
    timer.timeout.connect(_on_timer_timeout)

func _on_timer_timeout():
    visible = not visible
```

```csharp
public override void _Ready()
{
    var timer = GetNode<Timer>("Timer");
    timer.Timeout += OnTimerTimeout;
}

private void OnTimerTimeout()
{
    Visible = !Visible;
}
```

In GDScript, `timer.timeout.connect(callable)` treats the signal as an object with a `connect()` method — no strings involved, so your IDE can autocomplete both the signal name and the callback. In C#, signals map onto C# events, so you hook them up with `+=` (and detach with `-=`).

`_ready()` is the natural place to set up these connections, since it runs once the node and its children are fully in the tree.

### Disconnecting and one-shot connections

You can tear down a connection with `disconnect()`:

```gdscript
timer.timeout.disconnect(_on_timer_timeout)
```

...though this is fairly rare — most connections just live for the lifetime of both nodes. If you only want a callback to fire once, pass the `CONNECT_ONE_SHOT` flag instead of manually disconnecting after the first call:

```gdscript
timer.timeout.connect(_on_timer_timeout, CONNECT_ONE_SHOT)
```

### Awaiting a signal

GDScript lets you suspend a function until a signal fires, using `await`:

```gdscript
await timer.timeout
print("timer finished")
```

This is handy for sequencing — e.g. waiting for an animation or a delay without setting up a separate callback method.

## Defining your own signals

Signals aren't just for built-in nodes — you declare custom ones in any script with the `signal` keyword:

```gdscript
extends Node2D

signal health_depleted

var health = 10
```

```csharp
public partial class Player : Node2D
{
    [Signal]
    public delegate void HealthDepletedEventHandler();

    private int _health = 10;
}
```

A couple of naming notes: custom signals show up in the Signals dock exactly like built-in ones, and by convention they're named as past-tense events (`health_depleted`, not `deplete_health`) since a signal represents something that *already happened*.

To fire one, call `emit()`:

```gdscript
func take_damage(amount):
    health -= amount
    if health <= 0:
        health_depleted.emit()
```

```csharp
public void TakeDamage(int amount)
{
    _health -= amount;
    if (_health <= 0)
        EmitSignal(SignalName.HealthDepleted);
}
```

### Passing data with a signal

Signals can carry arguments, declared in the signal definition itself:

```gdscript
signal health_changed(old_value, new_value)
```

```csharp
[Signal]
public delegate void HealthChangedEventHandler(int oldValue, int newValue);
```

These declared parameter names are mostly for documentation and editor tooling — they let the Signals dock generate a matching callback signature for you. Godot doesn't actually enforce them at emit time, so it's on you to pass the right values and the right count:

```gdscript
func take_damage(amount):
    var old_health = health
    health -= amount
    health_changed.emit(old_health, health)
```

```csharp
public void TakeDamage(int amount)
{
    int oldHealth = _health;
    _health -= amount;
    EmitSignal(SignalName.HealthChanged, oldHealth, _health);
}
```

Any connected callback just needs matching parameters:

```gdscript
func _on_health_changed(old_value, new_value):
    health_bar.value = new_value
```

## Where you'll run into signals

They're everywhere in Godot's built-in nodes, not just UI:

- `Area2D.body_entered` — something physical entered a detection zone (great for pickups, triggers, hazards).
- `Timer.timeout` — a countdown finished.
- `Button.pressed`, and similar UI signals for value changes, focus, resizing, etc.
- `Node.tree_entered` / `tree_exited` — lifecycle events as nodes enter or leave the scene tree.

Whenever you catch yourself wanting object A to directly call a method on object B just because something happened in A, it's usually worth asking whether a signal would keep them more loosely coupled instead.

---

Let me know if you'd like this saved to a specific file once a write-capable path is available, or if you want a version aimed at a different audience (e.g. more editor-workflow-focused for beginners, or code-only for experienced devs).
