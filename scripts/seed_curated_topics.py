"""Seeds hand-authored, comprehensive content for a handful of topics
directly into the DB - no LLM call, ever, for these. Reuses the exact same
tables/shapes as LLM-generated content (QuestionSetCache, TopicLabel,
SearchHistory), so the frontend needs zero special-casing: these topics are
just cache hits from the moment this script runs, indistinguishable in
shape from anything the pipeline would produce, except `curated: true` in
the response so the UI can say so honestly.

Usage:
    python scripts/seed_curated_topics.py

Safe to re-run - every insert is an upsert keyed by the normalized topic
(and, for search history, by user+topic).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime  # noqa: E402

from sqlmodel import Session, select  # noqa: E402

from app.agent.cache import save_to_cache  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import engine, init_db  # noqa: E402
from app.models.question_cache import QuestionSetCache  # noqa: E402, F401
from app.models.search_history import SearchHistory  # noqa: E402
from app.models.subtopic_progress import SubtopicProgress  # noqa: E402, F401
from app.models.topic_label import TopicLabel  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.generate import Difficulty, Question  # noqa: E402
from app.schemas.pipeline import EvalReport, GenerateResult, RunMetrics, SubtopicContent  # noqa: E402
from app.topic_key import normalize_topic  # noqa: E402

# ---------------------------------------------------------------------------
# Content. Each topic: display name, short button label, group category
# (topics sharing a category get grouped together on the search page - see
# context: "if past search has multiple java topics they should group"),
# and a list of subtopics. Each subtopic has "content" (a few paragraphs of
# reading material, shown above the accordion so this is a genuine one-stop
# read, not just an isolated Q&A list) and 8 question/answer pairs spanning
# easy/medium/hard.
# ---------------------------------------------------------------------------

TOPICS = [
    {
        "topic": "Java",
        "short_label": "Java Core",
        "category": "Java",
        "subtopics": [
            {
                "name": "Core OOP & Language Fundamentals",
                "content": (
                    "Java's object-oriented core rests on four pillars: encapsulation, inheritance, "
                    "polymorphism, and abstraction. Encapsulation bundles data with the methods that "
                    "operate on it, hiding internal state behind a public interface (private fields, "
                    "controlled getters/setters) so callers can't violate an object's invariants directly. "
                    "Inheritance lets a subclass reuse and extend a superclass's behavior via `extends`, "
                    "forming an \"is-a\" relationship, while composition (\"has-a\", holding a reference to "
                    "another object instead of extending it) is often the more flexible choice in modern "
                    "design since it avoids fragile deep hierarchies. Polymorphism means the same method "
                    "call can produce different behavior depending on an object's actual runtime type - the "
                    "backbone of extensible designs where new subclasses can be added without touching code "
                    "that only depends on the supertype. Abstraction focuses on what an object does rather "
                    "than how, expressed through abstract classes and interfaces.\n\n"
                    "Beyond OOP, Java's type system matters day to day: primitives (int, boolean, char, etc.) "
                    "are stored directly (on the stack, or inline inside objects) and have no methods, while "
                    "their boxed wrapper counterparts (Integer, Boolean, Character) are real objects usable "
                    "in collections and generics, with autoboxing/unboxing bridging the two automatically - "
                    "sometimes surprisingly, since boxed types compare by reference with `==` outside a small "
                    "cached range. Compilation produces platform-independent bytecode (.class files) that the "
                    "JVM interprets or JIT-compiles at runtime, which is what \"write once, run anywhere\" "
                    "actually refers to: the same bytecode runs unmodified on any platform with a compatible JVM."
                ),
                "questions": [
                    ("easy", "What is the difference between JDK, JRE, and JVM?",
                     "JVM (Java Virtual Machine) executes bytecode and provides the runtime environment. JRE (Java Runtime Environment) bundles the JVM plus the standard class libraries needed to run Java applications. JDK (Java Development Kit) includes the JRE plus development tools like javac (the compiler), jar, and debuggers - it's what you need to write and compile Java code, not just run it."),
                    ("easy", "What is the difference between == and .equals() in Java?",
                     "== compares references for objects (whether two variables point to the same object in memory) and compares values for primitives. .equals() is a method that can be overridden to compare logical/content equality - String and most wrapper classes override it to compare values. Without an override, Object's default .equals() falls back to == behavior."),
                    ("medium", "Why are Strings immutable in Java, and what are the practical benefits?",
                     "String objects can't be modified after creation - any \"modification\" (concatenation, replace, etc.) returns a new String. Benefits: thread-safety without synchronization (immutable objects are inherently safe to share across threads), safe use as HashMap keys (hashcode can be cached since it never changes), and enables the String pool (the JVM can safely reuse/intern identical string literals since none can be mutated to affect other references)."),
                    ("medium", "What's the difference between an abstract class and an interface?",
                     "An abstract class can have constructors, instance state (fields), and a mix of abstract and concrete methods, but a class can extend only one abstract class (single inheritance). An interface traditionally could only declare method signatures and constants, but since Java 8 it can also have default and static methods with implementations; a class can implement multiple interfaces. Use an abstract class for a shared base with common state/behavior; use an interface to define a contract multiple unrelated classes can fulfill."),
                    ("hard", "Explain method overloading vs overriding, and how the JVM resolves each.",
                     "Overloading is having multiple methods with the same name but different parameter lists in the same class - resolved at compile time based on the static types of the arguments (static/early binding). Overriding is a subclass providing a new implementation for a method inherited from its superclass with the same signature - resolved at runtime based on the actual object type (dynamic/late binding via the virtual method table), which is what enables polymorphism."),
                    ("easy", "What is the difference between a primitive type and a wrapper class in Java?",
                     "A primitive (int, double, boolean, char, etc.) stores its value directly with no object overhead and has no methods. A wrapper class (Integer, Double, Boolean, Character) is a full object wrapping a primitive value, usable anywhere an Object is required - such as in generics and collections, which can't hold primitives directly (List<int> isn't legal; List<Integer> is)."),
                    ("medium", "What is autoboxing, and where can it cause subtle bugs?",
                     "Autoboxing is the compiler's automatic conversion between a primitive and its wrapper type (int to Integer and back) so they can be used interchangeably in most contexts. It can cause subtle bugs: comparing two boxed Integers with == instead of .equals() works \"by accident\" for small cached values (-128 to 127, per the JVM's Integer cache) but fails for larger values since those aren't cached and are separate objects; and unboxing a null wrapper (e.g. a Map.get() miss) throws a NullPointerException at the point of unboxing, not obviously where you'd expect."),
                    ("hard", "What is the difference between composition and inheritance, and when should you prefer one?",
                     "Inheritance (\"is-a\") reuses a superclass's implementation by extending it, tightly coupling subclass to superclass - changes to the superclass can silently break subclasses (the fragile base class problem), and Java only allows single class inheritance. Composition (\"has-a\") reuses behavior by holding a reference to another object and delegating to it, which is more flexible (can be swapped/changed at runtime, no deep hierarchy) and is generally preferred - the common guidance is \"favor composition over inheritance\" and reserve inheritance for genuine is-a relationships with real shared behavior, not just code reuse convenience."),
                ],
            },
            {
                "name": "Collections Framework",
                "content": (
                    "The Java Collections Framework provides a unified set of interfaces and implementations "
                    "for storing and manipulating groups of objects. At the top sit four core interfaces: "
                    "List (an ordered, index-accessible, duplicate-allowing sequence - ArrayList, LinkedList), "
                    "Set (no duplicates - HashSet, LinkedHashSet, TreeSet), Map (key-value pairs, technically "
                    "outside the Collection interface hierarchy but part of the framework - HashMap, "
                    "LinkedHashMap, TreeMap), and Queue/Deque (ordered for processing, typically FIFO or "
                    "LIFO - ArrayDeque, PriorityQueue). Picking the right implementation is really about "
                    "picking the right performance tradeoffs and ordering guarantees for the access pattern "
                    "you actually have: random access by index favors ArrayList, frequent insertion/removal "
                    "at both ends favors ArrayDeque, guaranteed uniqueness with no order favors HashSet, and "
                    "sorted iteration favors a Tree-based structure.\n\n"
                    "Two things underpin correct use of hash-based collections (HashMap, HashSet): a solid "
                    "hashCode()/equals() contract on any custom key type, and understanding how collisions "
                    "and resizing affect performance (Java 8+ upgrades a bucket to a tree once it's crowded "
                    "enough, capping worst-case lookup at O(log n) instead of degrading to O(n)). Iteration "
                    "safety is another recurring theme: most collections are fail-fast, throwing "
                    "ConcurrentModificationException if structurally modified during iteration by anything "
                    "other than the iterator itself, while the java.util.concurrent collections (like "
                    "ConcurrentHashMap and CopyOnWriteArrayList) trade some consistency guarantees for safe "
                    "concurrent access without external locking."
                ),
                "questions": [
                    ("easy", "What is the difference between ArrayList and LinkedList?",
                     "ArrayList is backed by a dynamically-resized array - O(1) random access by index but O(n) insertion/removal in the middle (elements must shift). LinkedList is a doubly-linked list - O(1) insertion/removal once you have a reference to the node, but O(n) random access since you must traverse from an end. In practice, ArrayList is the better default for most use cases due to better cache locality."),
                    ("medium", "How does a HashMap work internally in Java?",
                     "A HashMap stores key-value pairs in an array of buckets. A key's hashCode() (after a supplemental hash function to spread bits) determines its bucket index. Collisions within a bucket are handled via a linked list, which Java 8+ converts to a red-black tree once a bucket exceeds a threshold (8 entries) for better worst-case lookup performance (O(log n) instead of O(n)). Resizing happens when the load factor (default 0.75) is exceeded, roughly doubling capacity and rehashing all entries."),
                    ("medium", "What's the difference between HashMap, LinkedHashMap, and TreeMap?",
                     "HashMap offers O(1) average access with no ordering guarantee. LinkedHashMap maintains insertion order (or access order, if configured) by threading a doubly-linked list through the entries. TreeMap keeps keys in sorted order (natural ordering or a supplied Comparator) by storing them in a red-black tree, giving O(log n) operations instead of O(1)."),
                    ("hard", "Why must objects used as HashMap keys have consistent hashCode() and equals()?",
                     "HashMap uses hashCode() to find the bucket and equals() to identify the exact key within that bucket. If two equal objects (per equals()) produce different hashCode() values, they could land in different buckets and the map would fail to recognize them as the same key - lookups, updates, and duplicate detection would silently break. The contract requires: equal objects must have equal hash codes (the reverse isn't required - unequal objects can share a hash code, that's just a collision)."),
                    ("hard", "What is the difference between fail-fast and fail-safe iterators?",
                     "Fail-fast iterators (ArrayList, HashMap, etc.) throw ConcurrentModificationException if the underlying collection is structurally modified while iterating (other than through the iterator's own remove()), detected via a modification counter. Fail-safe iterators (CopyOnWriteArrayList, ConcurrentHashMap) iterate over a snapshot or otherwise tolerate concurrent modification without throwing, at the cost of not necessarily reflecting the very latest state during iteration."),
                    ("medium", "What's the difference between Comparable and Comparator?",
                     "Comparable defines a class's single, natural ordering via compareTo() implemented on the class itself (e.g. String's natural alphabetical order). Comparator defines an external, arbitrary ordering via compare(), letting you sort the same type multiple different ways without modifying the class - useful when you need several orderings (by name, then separately by age) or can't modify the class at all."),
                    ("medium", "How does a HashSet ensure uniqueness internally?",
                     "HashSet is implemented as a thin wrapper around a HashMap, storing each element as a key mapped to a shared dummy constant value. Adding an element that's equal (per hashCode()/equals()) to an existing one simply overwrites that map entry rather than creating a duplicate - HashSet uniqueness is really HashMap key uniqueness underneath."),
                    ("hard", "What is the difference between Queue and Deque, and when would you use ArrayDeque over LinkedList as a stack/queue?",
                     "Queue supports insertion at one end and removal from the other (FIFO). Deque (double-ended queue) supports insertion and removal at both ends, so it can act as either a queue or a stack. ArrayDeque is generally preferred over LinkedList for both roles since it's backed by a resizable array with no per-node object overhead or pointer-chasing, giving better cache locality and lower memory overhead for the same O(1) amortized operations at both ends."),
                ],
            },
            {
                "name": "Concurrency & Multithreading",
                "content": (
                    "Concurrency lets a program make progress on multiple tasks by interleaving or "
                    "parallelizing their execution across threads, which matters both for responsiveness "
                    "(not blocking a UI thread on I/O) and throughput (using multiple CPU cores). The core "
                    "challenge is that threads within a process share the same heap, so uncoordinated "
                    "concurrent access to shared mutable state causes race conditions - the result depends "
                    "on unpredictable timing rather than program logic. Java's original tools for coordination "
                    "are the synchronized keyword (mutual exclusion via a monitor/object lock, plus a "
                    "happens-before memory-visibility guarantee) and volatile (visibility and ordering only, "
                    "no atomicity for compound operations like increment-and-check).\n\n"
                    "Writing correct low-level synchronized/wait/notify code is notoriously error-prone, "
                    "which is why the java.util.concurrent package (introduced in Java 5) exists: "
                    "ExecutorService and thread pools for managing reusable worker threads instead of raw "
                    "Thread objects, the atomic classes (AtomicInteger, AtomicReference) for lock-free "
                    "compare-and-swap-based updates to single variables, concurrent collections "
                    "(ConcurrentHashMap, CopyOnWriteArrayList) safe for concurrent access without external "
                    "locking, and higher-level coordination utilities like CountDownLatch and "
                    "Semaphore. Understanding deadlocks (circular waiting on locks), race conditions (result "
                    "depends on thread timing), and livelocks (threads keep changing state in response to "
                    "each other without making progress) - and how to avoid each - is central to writing "
                    "correct concurrent Java."
                ),
                "questions": [
                    ("easy", "What is the difference between a process and a thread?",
                     "A process is an independent execution unit with its own memory space; processes don't share memory directly and communication requires IPC. A thread is a lightweight unit of execution within a process; threads within the same process share the same heap and static memory, which makes communication easier but introduces the need for synchronization to avoid race conditions."),
                    ("medium", "What does the synchronized keyword do in Java?",
                     "It ensures mutual exclusion - only one thread can execute a synchronized block/method on a given monitor (object lock) at a time - and establishes a happens-before relationship, guaranteeing visibility of memory writes made before releasing the lock to the next thread that acquires it. It can be applied to instance methods (locks on `this`), static methods (locks on the Class object), or explicit blocks (locks on a specified object)."),
                    ("medium", "What is the volatile keyword, and how does it differ from synchronized?",
                     "volatile guarantees visibility (a write is immediately visible to other threads, preventing caching in registers/thread-local caches) and ordering (prevents instruction reordering around it), but does NOT provide atomicity for compound operations like increment. synchronized provides both visibility and mutual exclusion/atomicity, at a higher performance cost. volatile suits simple flags; synchronized (or java.util.concurrent) is needed for compound state changes."),
                    ("hard", "What's the difference between Runnable and Callable? Thread vs ExecutorService?",
                     "Runnable's run() returns nothing and can't throw checked exceptions. Callable's call() returns a value and can throw checked exceptions - used with ExecutorService to get a Future. Directly creating and starting Thread objects is low-level and doesn't reuse threads (expensive per-task); ExecutorService manages a pool of reusable threads, handles queuing, and is the recommended way to run concurrent tasks in real applications."),
                    ("hard", "What is a deadlock, and how would you typically prevent one?",
                     "A deadlock occurs when two or more threads each wait for a lock the other holds, so none can proceed - Thread A holds lock 1 and wants lock 2, while Thread B holds lock 2 and wants lock 1. Prevention: always acquire multiple locks in a consistent global order across all threads, use tryLock() with a timeout to back off instead of blocking indefinitely, minimize the scope/number of locks held simultaneously, or use higher-level java.util.concurrent utilities that avoid manual lock ordering entirely."),
                    ("easy", "What is a thread pool, and how does a fixed pool differ from a cached pool in ExecutorService?",
                     "A thread pool maintains a set of reusable worker threads that pick up submitted tasks from a queue, avoiding the overhead of creating/destroying a thread per task. Executors.newFixedThreadPool(n) keeps exactly n threads alive, queuing excess tasks - predictable resource usage, good for CPU-bound work. Executors.newCachedThreadPool() creates threads on demand and reuses idle ones (killing them after 60s of inactivity) - good for many short-lived, bursty I/O-bound tasks, but can create unbounded threads under sustained load."),
                    ("medium", "What is the java.util.concurrent.atomic package used for?",
                     "It provides classes like AtomicInteger, AtomicLong, and AtomicReference that support lock-free, thread-safe compound operations (increment-and-get, compare-and-set) on a single variable using CPU-level compare-and-swap instructions instead of locks. This avoids the overhead and contention of synchronized for simple counters/flags shared across threads, while still being fully thread-safe for that single variable."),
                    ("hard", "What is a race condition, and how does it differ from a deadlock?",
                     "A race condition occurs when the correctness of a result depends on the unpredictable timing/interleaving of concurrent operations on shared mutable state - e.g. two threads incrementing a non-atomic counter can lose an update. A deadlock is a liveness failure where threads are permanently blocked waiting on each other; a race condition is a correctness failure where the program runs to completion but can produce a wrong result. Both stem from inadequate synchronization, but they manifest completely differently - one hangs, the other silently corrupts data."),
                ],
            },
            {
                "name": "Exception Handling",
                "content": (
                    "Java's exception handling model forces (for checked exceptions) or allows (for "
                    "unchecked exceptions) callers to explicitly acknowledge that an operation might fail. "
                    "Checked exceptions (subclasses of Exception excluding RuntimeException, like "
                    "IOException) represent conditions a well-written program should anticipate and "
                    "recover from - the compiler enforces that you either catch them or declare them in a "
                    "throws clause. Unchecked exceptions (subclasses of RuntimeException, like "
                    "NullPointerException or IllegalArgumentException) generally represent programming "
                    "errors that shouldn't normally occur if the code is correct, so the compiler doesn't "
                    "force handling - forcing every caller to catch a NullPointerException everywhere would "
                    "just be noise.\n\n"
                    "The try/catch/finally structure lets code attempt an operation, handle specific failure "
                    "types distinctly, and guarantee cleanup regardless of outcome; try-with-resources "
                    "(Java 7+) automates that cleanup for anything implementing AutoCloseable, closing "
                    "resources in reverse declaration order even when an exception propagates. Good "
                    "exception design in larger systems is as much about API design as error handling: "
                    "catching only what you can meaningfully act on (not bare Exception/Throwable, which can "
                    "mask real bugs or even fatal JVM errors), preserving the original cause when translating "
                    "between abstraction layers via exception chaining, and creating custom exception types "
                    "when the built-in hierarchy doesn't communicate the actual failure clearly enough to "
                    "calling code."
                ),
                "questions": [
                    ("easy", "What is the difference between checked and unchecked exceptions?",
                     "Checked exceptions (subclasses of Exception, excluding RuntimeException) must be caught or declared in a method's throws clause - the compiler enforces handling, e.g. IOException. Unchecked exceptions (subclasses of RuntimeException, like NullPointerException) aren't required to be declared or caught - they typically represent programming errors rather than recoverable external conditions."),
                    ("medium", "What is the purpose of the finally block, and when does it NOT execute?",
                     "finally runs regardless of whether the try block completes normally, throws, or returns - used for guaranteed cleanup like closing resources. It will NOT execute if the JVM exits during the try/catch (e.g. System.exit() is called), if the thread is killed, or on a fatal JVM crash/power loss."),
                    ("medium", "What is try-with-resources, and what problem does it solve?",
                     "Introduced in Java 7, try-with-resources automatically closes any resource implementing AutoCloseable when the try block exits, in reverse order of declaration, even if an exception occurs - eliminating manual close() calls in a finally block and the common bug of forgetting to close a resource on the exception path."),
                    ("hard", "What is exception chaining, and why is it useful?",
                     "Exception chaining wraps a lower-level exception inside a higher-level one (via the cause constructor or initCause()) when translating between abstraction layers, e.g. catching a SQLException and rethrowing a custom DataAccessException with the SQLException as its cause. This preserves the original stack trace and root cause for debugging while letting calling code depend on a more meaningful, layer-appropriate exception type."),
                    ("hard", "Why is catching a bare Exception or Throwable generally discouraged?",
                     "Catching Exception broadly can accidentally swallow RuntimeExceptions that represent real bugs, masking problems instead of surfacing them, and obscures what failure modes the code actually anticipates. Catching Throwable is worse - it also catches Error subclasses like OutOfMemoryError, which generally indicate the JVM is in a state where continuing execution isn't safe. Catch the most specific exception type you can actually handle meaningfully."),
                    ("easy", "What is the difference between throw and throws?",
                     "throw is a statement used inside a method body to actually raise a specific exception instance at that point (`throw new IllegalArgumentException(\"bad input\")`). throws is a clause in a method's signature declaring that the method might propagate one or more checked exception types to its caller (`void read() throws IOException`), so the compiler can enforce that callers handle it."),
                    ("medium", "Can you catch multiple exception types in a single catch block?",
                     "Yes, using a multi-catch block: `catch (IOException | SQLException e)`. This is useful when several exception types should be handled identically, avoiding duplicated catch-block bodies - the caveat is the caught variable is effectively final and typed as the common supertype of the listed exceptions, so you can't reassign it or call a method specific to only one of the branches without an instanceof check."),
                    ("hard", "What is a custom exception, and when should you create one?",
                     "A custom exception is a class extending Exception (checked) or RuntimeException (unchecked) that represents a specific, meaningful failure in your domain (e.g. InsufficientFundsException) rather than a generic built-in type. Create one when a generic exception type wouldn't clearly communicate what went wrong to calling code, when you want to attach domain-specific data to the failure (like an account ID), or when you're translating a lower-level exception into something meaningful at your API's abstraction level."),
                ],
            },
            {
                "name": "Streams & Functional Programming",
                "content": (
                    "Java 8 introduced lambda expressions and the Stream API, bringing a functional style to "
                    "a traditionally imperative language. A lambda is a compact way to implement a functional "
                    "interface (an interface with exactly one abstract method, like Runnable or Comparator) "
                    "inline, without the ceremony of an anonymous class - this made it practical to pass "
                    "behavior as data throughout the standard library. The Stream API builds on this: a "
                    "stream represents a sequence of elements supporting a pipeline of intermediate "
                    "operations (map, filter, sorted, distinct) that transform the data declaratively, "
                    "followed by a terminal operation (collect, forEach, reduce, count) that actually "
                    "triggers execution and produces a result.\n\n"
                    "A crucial property is laziness: intermediate operations build up a pipeline description "
                    "but don't run anything until a terminal operation is invoked, which enables "
                    "optimizations like short-circuiting (findFirst() can stop as soon as a match is found "
                    "instead of processing the whole source). Streams pair naturally with Optional, which "
                    "represents a possibly-absent value explicitly in the type system rather than via "
                    "null, forcing callers to consciously handle the empty case. Streams can also run in "
                    "parallel via parallelStream(), splitting work across the common ForkJoinPool - powerful "
                    "for large, CPU-bound, side-effect-free operations, but risky if the operations aren't "
                    "genuinely stateless or touch shared mutable state, since that reintroduces the exact "
                    "concurrency bugs the functional style was meant to avoid."
                ),
                "questions": [
                    ("easy", "What is a lambda expression in Java, and what problem did it solve?",
                     "A lambda expression is a concise way to represent an instance of a functional interface (an interface with exactly one abstract method) without writing a full anonymous class. It reduces boilerplate for passing behavior as data, e.g. `list.forEach(x -> System.out.println(x))` instead of an anonymous class."),
                    ("medium", "What is the difference between map() and flatMap() in the Stream API?",
                     "map() transforms each element to exactly one other element (1-to-1). flatMap() transforms each element into a Stream of elements and flattens all those streams into a single stream (1-to-many, flattened) - used when each input maps to zero or more outputs, like flattening a List<List<String>> into a single Stream<String>."),
                    ("medium", "Are Java Streams lazy or eager, and why does it matter?",
                     "Intermediate operations (map, filter, sorted) are lazy - they build a pipeline but don't execute until a terminal operation (collect, forEach, reduce) is invoked. This allows short-circuiting (findFirst() can stop once a match is found) and avoids unnecessary work building intermediate collections at each stage."),
                    ("hard", "What is the difference between Optional.of(), Optional.ofNullable(), and Optional.empty()?",
                     "Optional.of(value) throws NullPointerException immediately if value is null - use it when certain the value is non-null. Optional.ofNullable(value) safely wraps a possibly-null value, producing Optional.empty() if null. Optional.empty() explicitly creates an empty Optional. The pattern forces callers to explicitly handle the absent case rather than risking a NullPointerException."),
                    ("hard", "Can Stream operations be safely parallelized with parallelStream()? What are the risks?",
                     "parallelStream() splits the source and processes chunks on the ForkJoinPool's common pool, which can help for large, CPU-bound, stateless operations on splittable sources. Risks: operations must be stateless and the combining function associative, or results become non-deterministic; shared mutable state accessed inside the stream needs synchronization (defeating the purpose); splitting/merging overhead can make small streams slower in parallel; and it competes with other code using the shared common pool."),
                    ("easy", "What is a method reference, and how does it relate to lambdas?",
                     "A method reference (e.g. `String::toUpperCase` or `System.out::println`) is shorthand syntax for a lambda that does nothing but call an existing method. It's purely syntactic sugar - `s -> s.toUpperCase()` and `String::toUpperCase` compile to the same functional interface implementation - used whenever the lambda body would just be \"call this one existing method.\""),
                    ("medium", "What is the difference between Collectors.toList() and Collectors.groupingBy()?",
                     "Collectors.toList() collects stream elements into a single flat List. Collectors.groupingBy() partitions elements into a Map keyed by a classifier function's result, with each key mapping to a List of elements sharing that key (or a further downstream collector's result) - used whenever you need to bucket a stream's elements by some property, like grouping questions by subtopic."),
                    ("hard", "What is a functional interface, and can you give an example beyond Runnable?",
                     "A functional interface has exactly one abstract method (it may have any number of default/static methods), making it a valid target type for a lambda expression or method reference; the optional @FunctionalInterface annotation lets the compiler enforce this. Beyond Runnable, java.util.function provides many general-purpose ones: Function<T,R> (takes T, returns R), Predicate<T> (takes T, returns boolean), Consumer<T> (takes T, returns void), and Supplier<T> (takes nothing, returns T) - the building blocks the Stream API's methods (map, filter, forEach) are typed against."),
                ],
            },
            {
                "name": "Memory Management & JVM",
                "content": (
                    "The JVM divides memory into distinct regions with different lifetimes and purposes. "
                    "Each thread gets its own stack, holding method call frames, local variables, and "
                    "primitives - automatically reclaimed the instant a method returns, no garbage collector "
                    "involved. The heap, shared across all threads, holds every object ever created with "
                    "`new`, and is where the garbage collector actually does its work: identifying objects no "
                    "longer reachable from any GC root (active thread stacks, static fields, JNI references) "
                    "and reclaiming their memory, since Java uses reachability-based tracing rather than "
                    "simple reference counting (which can't handle circular references cleanly).\n\n"
                    "The heap itself is generationally divided based on the empirical observation that most "
                    "objects die young: new allocations go into the Young Generation (an Eden space plus two "
                    "Survivor spaces), where frequent, cheap Minor GCs run; objects that survive several "
                    "rounds get promoted into the Old Generation, collected less often but at higher cost per "
                    "collection since it holds larger, longer-lived objects. Modern collectors (G1, the "
                    "default in recent JVM versions; ZGC and Shenandoah for very low pause-time requirements) "
                    "differ mainly in how they trade off throughput against pause-time predictability. Even "
                    "with automatic GC, memory leaks are possible - an object that's logically unneeded but "
                    "still reachable (held in a static collection that's never cleared, a listener that's "
                    "never unregistered) can never be collected, since \"reachable\" is all the GC actually "
                    "checks. Java also exposes different reference strengths (strong, soft, weak, phantom) "
                    "for cases where you want to hint that an object is collectible under specific conditions, "
                    "rather than relying purely on plain reachability."
                ),
                "questions": [
                    ("easy", "What is the difference between the stack and the heap?",
                     "The stack stores method call frames, local variables, and primitives - each thread has its own stack, reclaimed automatically when a method returns. The heap stores all objects and is shared across all threads - reclaimed by the garbage collector, not automatically on scope exit."),
                    ("medium", "What is garbage collection, and what makes an object eligible for it?",
                     "Garbage collection automatically reclaims heap memory occupied by objects no longer reachable from any GC root (active thread stacks, static fields, JNI references). An object becomes eligible once there's no reachable reference chain to it from any root - Java uses reachability-based tracing, not simple reference counting (which can't handle circular references)."),
                    ("medium", "What is the difference between the Young Generation and Old Generation?",
                     "The heap is generationally divided since most objects die young. New objects go in the Young Generation (Eden + two Survivor spaces); cheap, frequent Minor GCs run here. Objects surviving several minor GCs get promoted to the Old Generation, collected less often but with a more expensive Major/Full GC, since it typically holds larger, longer-lived objects."),
                    ("hard", "What is a memory leak in Java, given that it has garbage collection?",
                     "Even with GC, a leak happens when objects are no longer needed by application logic but remain reachable (so GC can't reclaim them) - e.g. objects held in a static collection that's never cleared, unclosed resources registering listeners that hold references back to large objects, or caches with no eviction. GC only frees what's unreachable; it can't determine \"unneeded but still referenced.\""),
                    ("hard", "What's the difference between strong, weak, soft, and phantom references?",
                     "A strong reference (default) prevents GC entirely while it exists. A soft reference allows collection, but only under memory pressure - useful for memory-sensitive caches. A weak reference doesn't prevent collection at all - collected as soon as no strong references remain (e.g. WeakHashMap). A phantom reference is enqueued only after the object has already been finalized, used for scheduling cleanup rather than accessing the object (get() always returns null)."),
                    ("medium", "What is the Metaspace, and how does it differ from PermGen in older JVMs?",
                     "Metaspace (Java 8+) stores class metadata (loaded class definitions, method info) and lives in native memory outside the heap, growing dynamically by default. It replaced PermGen, which was a fixed-size region within the heap in Java 7 and earlier that frequently caused OutOfMemoryError: PermGen space in applications that loaded many classes dynamically (like app servers redeploying webapps) - Metaspace's dynamic native-memory growth largely eliminated that specific failure mode."),
                    ("hard", "What garbage collectors are available in modern JVMs, and how do they differ (e.g., G1 vs ZGC)?",
                     "G1 (Garbage First, the default since Java 9) divides the heap into many regions and prioritizes collecting the ones with the most garbage first, balancing throughput and pause times for typical application heaps. ZGC and Shenandoah are designed for very large heaps with strict low-pause requirements, using techniques like concurrent (mostly non-stop-the-world) compaction to keep pauses in the single-digit milliseconds regardless of heap size, at some cost in raw throughput and CPU overhead compared to G1."),
                    ("hard", "What causes an OutOfMemoryError vs a StackOverflowError?",
                     "OutOfMemoryError (heap space) occurs when the heap is full of still-reachable objects and the JVM genuinely can't allocate more, even after a full GC - typically from a memory leak, too-small heap sizing, or legitimately loading more data than fits. StackOverflowError occurs when a thread's call stack exceeds its fixed size limit, almost always from uncontrolled recursion (missing or wrong base case) rather than a memory-sizing issue - increasing heap size doesn't help; the stack is a separate, per-thread region."),
                ],
            },
            {
                "name": "Generics",
                "content": (
                    "Generics let classes, interfaces, and methods be parameterized by type, so the compiler "
                    "can enforce type correctness at compile time instead of deferring failures to a runtime "
                    "ClassCastException. Before generics, collections stored plain Object references; "
                    "retrieving an element required an explicit downcast that the compiler couldn't verify "
                    "was safe. With `List<Integer>`, the compiler guarantees every element really is an "
                    "Integer, and removes the need for manual casts entirely. Generic type parameters "
                    "(conventionally single letters like T, E, K, V) can be bounded (`<T extends Number>`) to "
                    "require the type support specific operations, and wildcards (`? extends T`, `? super T`) "
                    "express variance - what you can safely read versus write from/to a generically-typed "
                    "reference, summarized by the mnemonic PECS: Producer Extends, Consumer Super.\n\n"
                    "A subtlety that trips up many developers is type erasure: generic type information "
                    "exists only at compile time for type-checking purposes and is erased from the actual "
                    "bytecode, replaced by the type's bound (or Object if unbounded), with the compiler "
                    "inserting casts automatically where needed. This is a deliberate backward-compatibility "
                    "decision (so generic code interoperates with pre-generics bytecode) but has real "
                    "consequences: you can't do `new T()` or check `instanceof List<String>` at runtime (only "
                    "the raw `instanceof List`), and you can't create an array of a generic type directly, "
                    "since arrays retain runtime type information that generics don't have to check against."
                ),
                "questions": [
                    ("easy", "What problem do Java generics solve?",
                     "Before generics, collections stored Object references, requiring explicit casts on retrieval and offering no compile-time type safety - putting a String into a \"List of Integers\" would only fail at runtime on a cast. Generics let you parameterize types (List<Integer>) so the compiler enforces type correctness at compile time and eliminates manual casting."),
                    ("medium", "What is type erasure in Java generics?",
                     "Generic type information exists only at compile time for type-checking; the compiler erases it and replaces type parameters with their bounds (or Object) in the compiled bytecode, inserting casts where needed. This is why you can't do `new T()`, can't check `instanceof List<String>` (only raw `instanceof List`), and can't create generic arrays directly."),
                    ("medium", "What's the difference between `List<? extends T>` and `List<? super T>`?",
                     "`List<? extends T>` is an upper-bounded wildcard - you can read T (or a subtype) safely, but can't add to it (except null), since the actual list could be any subtype of T. `List<? super T>` is lower-bounded - you can safely add T (or a subtype), but reading only guarantees an Object. This is the PECS rule: Producer Extends, Consumer Super."),
                    ("hard", "Why can't you create an array of a generic type, like `new T[10]`?",
                     "Arrays are covariant and carry runtime type information (checking element types on each write), but generics use type erasure and have no runtime type information. Allowing `new T[10]` would let you circumvent generic type safety - you could store an incompatible type via the array's erased Object[] runtime type without the array's own checks catching it."),
                    ("hard", "What is a bounded type parameter, and why use one?",
                     "A bounded type parameter restricts what types can be substituted, e.g. `<T extends Comparable<T>>` requires T to implement Comparable<T>. This lets you call methods from the bound (like compareTo()) directly on values of type T inside the generic method/class, which wouldn't be possible with an unbounded `<T>` since the compiler only knows T is some Object subtype."),
                    ("easy", "What is a raw type, and why should it be avoided?",
                     "A raw type is a generic class or interface used without its type parameter, e.g. `List list = new ArrayList()` instead of `List<String>`. It disables all compile-time generic type checking for that variable, reintroducing the exact ClassCastException risk generics were designed to eliminate - raw types exist only for backward compatibility with pre-generics code and should never be used in new code."),
                    ("medium", "Can generic methods have their own type parameters independent of the class?",
                     "Yes - a method can declare its own type parameter(s) before the return type, e.g. `static <T> T firstElement(List<T> list)`, independent of whether the enclosing class is itself generic. This is common for static utility methods (like Collections.sort or a generic firstNonNull helper) where the type parameter only needs to exist for that one method call, inferred from the arguments passed."),
                    ("hard", "What is the difference between an unbounded wildcard `<?>` and a raw type?",
                     "Both look similarly permissive, but an unbounded wildcard (`List<?>`) still fully participates in generic type checking - the compiler just doesn't know the specific element type, so it disallows adding anything except null (since it can't verify the addition matches whatever the actual, unknown type parameter is). A raw type (`List`) disables generic checking entirely, allowing you to add anything at all with no compile-time safety, which is exactly the unsafe behavior `<?>` was designed to prevent while still allowing generic APIs to accept \"a List of some type I don't need to know.\""),
                ],
            },
        ],
    },
    {
        "topic": "Spring Boot",
        "short_label": "Spring Boot",
        "category": "Java",
        "subtopics": [
            {
                "name": "Core Concepts & Auto-Configuration",
                "content": (
                    "Spring Boot builds on top of the core Spring Framework to eliminate the manual "
                    "configuration burden that made plain Spring applications tedious to bootstrap. Where "
                    "classic Spring required explicit XML or Java configuration wiring every bean - a "
                    "DataSource, a DispatcherServlet, a Jackson ObjectMapper - Spring Boot's auto-configuration "
                    "mechanism inspects what's on the classpath and conditionally registers sensible default "
                    "beans for you. Adding the spring-boot-starter-web dependency, for instance, is enough to "
                    "get a fully configured embedded Tomcat server and Spring MVC stack with zero explicit "
                    "setup. The single `@SpringBootApplication` annotation you put on your main class is "
                    "itself a convenience bundling three separate annotations: `@Configuration` (this class "
                    "can define beans), `@EnableAutoConfiguration` (turn on the classpath-driven "
                    "auto-configuration machinery), and `@ComponentScan` (scan this package and below for "
                    "Spring-managed components).\n\n"
                    "Under the hood, auto-configuration classes are guarded by conditional annotations - "
                    "`@ConditionalOnClass` (only apply if a given class is present on the classpath), "
                    "`@ConditionalOnMissingBean` (only apply if the developer hasn't already defined their own "
                    "bean of that type, so user configuration always wins over the default), and "
                    "`@ConditionalOnProperty` (only apply if a config property has a specific value). This "
                    "design is what makes Spring Boot \"opinionated but overridable\": you get working "
                    "defaults for the common case, but any default can be selectively replaced or excluded "
                    "the moment your application needs something different, without fighting the framework."
                ),
                "questions": [
                    ("easy", "What is Spring Boot, and how does it differ from the Spring Framework?",
                     "Spring Framework is a comprehensive framework for building Java applications, providing dependency injection, AOP, and integration modules, but requires significant manual configuration to wire everything together. Spring Boot is built on top of Spring and adds auto-configuration, embedded servers (Tomcat/Jetty/Undertow), opinionated \"starter\" dependencies, and production-ready features (Actuator), so you can get a working application running with minimal explicit configuration."),
                    ("easy", "What does the @SpringBootApplication annotation do?",
                     "It's a convenience meta-annotation combining three: @Configuration (marks the class as a source of bean definitions), @EnableAutoConfiguration (triggers Spring Boot's auto-configuration based on classpath contents), and @ComponentScan (scans the current package and sub-packages for Spring-managed components)."),
                    ("medium", "How does Spring Boot's auto-configuration mechanism actually work?",
                     "Auto-configuration classes are conditionally applied based on annotations like @ConditionalOnClass (a class is present on the classpath), @ConditionalOnMissingBean (no bean of that type is already defined), and @ConditionalOnProperty (a config property has a specific value). Spring Boot only activates candidates whose conditions are satisfied, so adding spring-boot-starter-data-jpa automatically configures a DataSource and EntityManager if none is user-defined."),
                    ("medium", "What is a Spring Boot \"starter\" dependency?",
                     "A starter is a curated dependency descriptor bundling a set of compatible libraries for a specific purpose - e.g. spring-boot-starter-web pulls in Spring MVC, an embedded Tomcat, and Jackson for JSON. Starters remove the need to manually track compatible version combinations of related libraries."),
                    ("hard", "How would you exclude a specific auto-configuration class you don't want applied?",
                     "Use `@SpringBootApplication(exclude = {DataSourceAutoConfiguration.class})` (or the `exclude` attribute on `@EnableAutoConfiguration`), or set `spring.autoconfigure.exclude` in application.properties/yml - useful when you want to configure something like the DataSource entirely manually instead of letting Boot infer it."),
                    ("easy", "What is Spring Boot Actuator, and what does it provide out of the box?",
                     "Actuator is a starter that adds production-ready monitoring/management endpoints (like /actuator/health, /actuator/metrics, /actuator/info) to a Spring Boot application with minimal configuration, exposing things like application health, JVM metrics, and environment details - useful for operations tooling, load balancer health checks, and observability without hand-building those endpoints."),
                    ("medium", "What is the difference between application startup via `java -jar` and running an embedded server, versus deploying a WAR to an external servlet container?",
                     "Spring Boot's default packaging is an executable \"fat\" JAR containing an embedded servlet container (Tomcat by default), so `java -jar app.jar` starts a fully self-contained running application with no separate server installation needed. The traditional alternative - packaging as a WAR and deploying it into an externally managed servlet container (like a standalone Tomcat or WildFly install) - is still supported but is now the less common path, mainly used when an organization mandates a shared external container."),
                    ("hard", "What is the difference between CommandLineRunner and ApplicationRunner, and when would you use either?",
                     "Both are functional interfaces for running code immediately after the Spring application context has fully started, implemented as a bean and auto-invoked by Spring Boot. CommandLineRunner receives raw String[] args exactly as passed to main(). ApplicationRunner receives a parsed ApplicationArguments object distinguishing option arguments (--key=value) from plain positional ones. Use either for startup tasks like seeding data or warming a cache; ApplicationRunner is preferable when you actually need to interpret named CLI flags rather than just raw strings."),
                ],
            },
            {
                "name": "Dependency Injection & Bean Lifecycle",
                "content": (
                    "Dependency injection (DI) is the design pattern at the heart of the Spring Framework: "
                    "instead of a class constructing its own collaborators with `new`, those dependencies are "
                    "supplied ('injected') from the outside by a container - the Spring IoC (Inversion of "
                    "Control) container. This inverts the traditional flow of control (hence the name): the "
                    "framework calls your code and hands it what it needs, rather than your code reaching out "
                    "and pulling in concrete dependencies itself. The payoff is testability (a mock can be "
                    "injected in place of a real dependency in a unit test) and flexibility (swapping an "
                    "implementation, like a different payment gateway, doesn't require touching the classes "
                    "that depend on it - only the wiring).\n\n"
                    "Spring detects injectable classes via stereotype annotations (`@Component` and its "
                    "specializations `@Service`, `@Repository`, `@Controller`), then wires their declared "
                    "dependencies together using one of three injection styles: constructor injection "
                    "(dependencies passed via the constructor, generally preferred since it makes "
                    "dependencies explicit, supports `final` fields, and fails fast at startup if something's "
                    "missing), setter injection (via a setter method, useful for optional dependencies), or "
                    "field injection (`@Autowired` directly on a field, concise but harder to unit test "
                    "without the framework and easy to misuse for hidden, implicit dependencies). Beans "
                    "default to singleton scope (one shared instance per container), though prototype, "
                    "request, and session scopes exist for cases needing a fresh instance per lookup, HTTP "
                    "request, or user session respectively. Spring also manages a bean's full lifecycle - "
                    "instantiation, dependency injection, post-construction callbacks (`@PostConstruct`), "
                    "and pre-destruction cleanup (`@PreDestroy`) - giving hooks at each stage without manual "
                    "bookkeeping."
                ),
                "questions": [
                    ("easy", "What is dependency injection, and what problem does it solve?",
                     "Dependency injection is a pattern where an object's dependencies are provided by an external source (the Spring IoC container) rather than the object creating them itself. It solves tight coupling - classes depend on abstractions provided to them, making code more testable (dependencies can be mocked) and flexible (implementations can be swapped)."),
                    ("medium", "What's the difference between @Component, @Service, @Repository, and @Controller?",
                     "All four are specializations of @Component, picked up by component scanning identically for bean registration - the distinction is mostly semantic, plus some added behavior: @Repository additionally enables translation of persistence-layer exceptions into Spring's DataAccessException hierarchy; @Controller marks a Spring MVC web controller; @Service conventionally marks business-logic classes with no extra framework behavior beyond @Component."),
                    ("medium", "What's the difference between constructor injection and field injection? Which is preferred?",
                     "Field injection (@Autowired on a field) is concise but makes the class harder to unit test without Spring and hides required dependencies. Constructor injection makes dependencies explicit and immutable (final fields), fails fast at startup if a dependency is missing, and works cleanly with plain unit tests via `new MyClass(mockDep)`. Constructor injection is generally preferred, and Spring even lets you skip @Autowired on a single constructor."),
                    ("hard", "What are the Spring bean scopes, and when would you use something other than the default?",
                     "The default is singleton - one shared instance per container. prototype creates a new instance every time the bean is requested. request and session scopes (web-aware) create one instance per HTTP request/session. Use prototype for stateful, non-thread-safe beans that shouldn't be shared, and request/session scope for per-request or per-user state that shouldn't leak across users."),
                    ("hard", "What is a circular dependency in Spring, and how can it be resolved?",
                     "A circular dependency occurs when Bean A needs Bean B and Bean B needs Bean A (directly or transitively). With constructor injection, this fails outright at startup since neither can be fully constructed first. Spring can resolve it for singletons via setter/field injection using early bean references, but the better fix is usually to refactor - extract shared logic into a third bean both depend on - since circular dependencies often indicate a design smell."),
                    ("easy", "What do @PostConstruct and @PreDestroy do?",
                     "@PostConstruct marks a method to run once, right after Spring finishes constructing a bean and injecting its dependencies - useful for initialization logic that needs those dependencies already set. @PreDestroy marks a method to run once, right before a singleton bean is destroyed as the application context shuts down - useful for cleanup like closing a connection pool. Neither applies reliably to prototype-scoped beans, since Spring doesn't manage their full lifecycle after creation."),
                    ("medium", "What is the difference between @Autowired and @Qualifier?",
                     "@Autowired tells Spring to inject a matching bean by type; if multiple beans of the same type exist, Spring can't decide which one and throws a NoUniqueBeanDefinitionException. @Qualifier, used alongside @Autowired, disambiguates by specifying the exact bean name to inject when multiple candidates of the same type are registered - e.g. two different DataSource beans for two databases."),
                    ("hard", "What is a Spring @Configuration class, and how does it differ from a plain @Component that happens to have @Bean methods?",
                     "A @Configuration class is CGLIB-proxied by Spring so that calling one @Bean method from another within the same class returns the same singleton instance rather than creating a fresh object each call, correctly preserving singleton semantics for beans that depend on each other. A plain class annotated only @Component (not @Configuration) with @Bean methods (\"lite\" mode) skips this proxying - calling one @Bean method from another inside it directly invokes the Java method, creating a new instance every time rather than reusing the container-managed singleton, which is a common source of subtle bugs if the distinction isn't understood."),
                ],
            },
            {
                "name": "Spring MVC & REST",
                "content": (
                    "Spring MVC is the web framework underlying most Spring Boot REST APIs, built around a "
                    "central front-controller servlet called `DispatcherServlet`. Every incoming HTTP request "
                    "passes through it first: it consults a `HandlerMapping` to find which controller method "
                    "should handle the request, invokes that method via a `HandlerAdapter`, and then - for a "
                    "traditional view-based controller - resolves a logical view name into an actual template "
                    "via a `ViewResolver`, or - for a REST controller - serializes the return value directly "
                    "into the response body via a registered `HttpMessageConverter` (Jackson for JSON, by "
                    "default). `@RestController` is simply `@Controller` plus `@ResponseBody` applied to "
                    "every method, which is why REST controllers skip the view-resolution step entirely.\n\n"
                    "Extracting data from a request uses purpose-specific annotations: `@PathVariable` for a "
                    "templated URI segment (`/users/{id}`), `@RequestParam` for a query string or form "
                    "parameter (`/users?id=5`), and `@RequestBody` for deserializing an entire JSON payload "
                    "into a Java object. Error handling is centralized rather than repeated per-controller "
                    "via `@ExceptionHandler` methods, typically grouped in a global `@RestControllerAdvice` "
                    "class that intercepts specific exception types thrown anywhere in the application and "
                    "converts them into a consistent, properly-statused error response shape. Designing a "
                    "clean REST API also means thinking about resource naming (nouns, not verbs, in URIs), "
                    "correct HTTP method/status code usage, and a versioning strategy for evolving the API "
                    "without breaking existing clients."
                ),
                "questions": [
                    ("easy", "What is the difference between @RestController and @Controller?",
                     "@Controller is for traditional Spring MVC controllers that return view names resolved to templates (like Thymeleaf). @RestController combines @Controller and @ResponseBody, so every method's return value is serialized directly into the HTTP response body (typically JSON), rather than interpreted as a view name."),
                    ("medium", "What's the difference between @RequestParam, @PathVariable, and @RequestBody?",
                     "@RequestParam extracts a value from the query string or form data (e.g. /users?id=5). @PathVariable extracts a value from a templated URI segment (e.g. /users/{id}). @RequestBody deserializes the entire HTTP request body (typically JSON) into a Java object, used for POST/PUT payloads."),
                    ("medium", "How does Spring MVC handle exceptions thrown from a controller method?",
                     "By default, unhandled exceptions produce a generic error response. You can define an @ExceptionHandler method within a controller (or globally via @ControllerAdvice/@RestControllerAdvice) to catch specific exception types and return a custom, appropriately-structured error response with the right HTTP status code, centralizing error handling instead of repeating try/catch in every controller."),
                    ("hard", "What is the role of DispatcherServlet in Spring MVC?",
                     "DispatcherServlet is the front controller that receives every incoming HTTP request. It consults a HandlerMapping to determine which controller method should handle the request, invokes it via a HandlerAdapter, then uses a ViewResolver (or, for @RestController, the configured HttpMessageConverters) to produce the final response - the central orchestrator of the whole MVC request-processing pipeline."),
                    ("hard", "How would you version a REST API in Spring Boot, and what are the tradeoffs?",
                     "Common approaches: URI versioning (/api/v1/users) - simple and visible, but pollutes the URI; header/media-type versioning (Accept: application/vnd.myapp.v1+json) - clean URIs but less discoverable; query parameter versioning (?version=1) - simple but easy to omit. URI versioning is most common in practice due to its simplicity and visibility, despite being less \"RESTfully pure.\""),
                    ("easy", "What does @RequestMapping (and its shortcuts like @GetMapping) do?",
                     "@RequestMapping maps an HTTP request to a specific controller method (or class-level, a base path for all its methods), optionally restricted by HTTP method, headers, or content type. @GetMapping, @PostMapping, @PutMapping, @DeleteMapping, and @PatchMapping are shorthand meta-annotations for @RequestMapping pre-restricted to that one HTTP method - more concise and self-documenting than always writing the full form."),
                    ("medium", "How does Spring validate request payloads, and where do validation errors surface?",
                     "Annotating a @RequestBody parameter with @Valid (or @Validated) triggers Bean Validation (JSR 380) against constraint annotations on the target class's fields (@NotNull, @Size, @Email, etc.). If validation fails, Spring throws a MethodArgumentNotValidException before the controller method body even runs, which by default produces a 400 response - typically caught in a global @ExceptionHandler to shape a clean, field-level error response instead of the framework's default."),
                    ("hard", "What is content negotiation in Spring MVC, and how does it decide what format to return?",
                     "Content negotiation determines the response representation format (JSON, XML, etc.) based on what the client requests, primarily via the Accept header, though Spring can also consider a URL suffix or query parameter depending on configuration. Spring MVC picks the best-matching HttpMessageConverter registered for that media type - by default, most Spring Boot REST APIs only register Jackson for JSON, so content negotiation is effectively moot until additional converters (like an XML one) are explicitly added to the classpath/configuration."),
                ],
            },
            {
                "name": "Spring Data JPA",
                "content": (
                    "Spring Data JPA removes most of the repetitive boilerplate involved in writing a "
                    "persistence layer on top of JPA (the Java Persistence API) and Hibernate (its most "
                    "common implementation). Rather than writing a DAO class with hand-coded CRUD methods, "
                    "you declare a repository interface extending `JpaRepository<Entity, IdType>`, and Spring "
                    "generates a working implementation at runtime automatically - `save()`, `findById()`, "
                    "`findAll()`, `deleteById()`, and more, all for free. Beyond the built-in methods, Spring "
                    "Data can derive entirely custom queries just from a method's name: `findByLastNameAndAge"
                    "GreaterThan(String lastName, int age)` is parsed against a recognized vocabulary of "
                    "keywords and automatically turned into the equivalent JPQL query at startup, with no SQL "
                    "or implementation code written by hand.\n\n"
                    "For anything method-name derivation can't express cleanly, `@Query` lets you write "
                    "explicit JPQL (portable across databases, operating on entity objects) or a native "
                    "query (raw, database-specific SQL) directly on a repository method. A recurring "
                    "performance pitfall in this layer is the N+1 select problem: lazily-loaded associations "
                    "(the default for `@OneToMany`/`@ManyToMany`, though notably NOT for `@ManyToOne`/"
                    "`@OneToOne`, which default to eager) trigger one extra query per parent entity when "
                    "accessed in a loop, turning what should be one query into N+1. The fix is almost always "
                    "an explicit `JOIN FETCH` in a JPQL query or an `@EntityGraph` annotation, rather than "
                    "blanket-switching everything to eager loading, which just relocates the same problem "
                    "elsewhere."
                ),
                "questions": [
                    ("easy", "What is Spring Data JPA, and what problem does it solve?",
                     "Spring Data JPA sits on top of JPA/Hibernate and eliminates most boilerplate DAO code by letting you define a repository interface (extending JpaRepository or CrudRepository) - Spring generates the implementation at runtime, providing CRUD operations and query derivation from method names without writing SQL or implementation code for common cases."),
                    ("medium", "How does Spring Data JPA derive a query from a method name like findByLastNameAndAgeGreaterThan?",
                     "Spring Data parses the method name against a set of keywords (By, And, Or, GreaterThan, Like, OrderBy, etc.) following the entity's property names, and builds the corresponding JPQL query automatically at startup, with parameters bound positionally to the method arguments."),
                    ("medium", "What's the difference between @Query with JPQL versus a native query?",
                     "@Query with JPQL operates on entity objects and their fields, is database-agnostic (Hibernate translates it to the appropriate SQL dialect), and is the default. A native query (`@Query(nativeQuery = true)`) is raw SQL specific to your actual database - useful for database-specific features or complex queries JPQL can't express, at the cost of portability."),
                    ("hard", "What is the N+1 select problem in JPA/Hibernate, and how do you fix it?",
                     "It occurs when fetching N parent entities lazily triggers N additional queries to fetch each one's related child entities individually (1 + N queries), instead of one efficient join. Fixes: use `JOIN FETCH` in a JPQL query to eagerly fetch the association in one query, use `@EntityGraph` to declaratively specify what to fetch eagerly per query, or adjust fetch type where appropriate - though changing to EAGER globally can introduce the same problem elsewhere."),
                    ("hard", "What's the difference between FetchType.LAZY and FetchType.EAGER, and what are the defaults?",
                     "LAZY defers loading the association until accessed (via a proxy), generally preferred for performance. EAGER loads the association immediately with the owning entity. By default, @OneToMany and @ManyToMany are LAZY, while @ManyToOne and @OneToOne are EAGER - a common source of N+1 problems is not realizing @ManyToOne defaults to eager loading."),
                    ("easy", "What is the difference between CrudRepository, PagingAndSortingRepository, and JpaRepository?",
                     "CrudRepository provides the basic CRUD operations (save, findById, findAll, delete). PagingAndSortingRepository extends it with paginated and sorted retrieval methods. JpaRepository extends PagingAndSortingRepository further with JPA-specific extras like batch operations and flushing - in practice, most Spring Boot projects just extend JpaRepository directly to get everything."),
                    ("medium", "What is the purpose of @Transactional, and what does \"propagation\" control?",
                     "@Transactional demarcates a method (or class) as running within a database transaction, managed by Spring so you don't manually open/commit/rollback connections - a runtime exception by default triggers an automatic rollback. Propagation controls how a transactional method behaves when called from within an already-active transaction: REQUIRED (the default) joins the existing one; REQUIRES_NEW suspends it and starts an independent one; NOT_SUPPORTED runs non-transactionally, suspending any active transaction."),
                    ("hard", "What is the first-level (persistence context) cache in JPA, and how does it differ from a second-level cache?",
                     "The first-level cache is tied to a single EntityManager/session: within one transaction, repeatedly loading the same entity by ID returns the same in-memory instance without hitting the database again, and it's always on with no configuration. A second-level cache (like Hibernate's, backed by Ehcache or similar) is shared across sessions/transactions and must be explicitly enabled and configured per entity - it caches entity state across the whole application, reducing database load for frequently-read, rarely-changed data, at the cost of needing an explicit invalidation strategy when the underlying data changes elsewhere."),
                ],
            },
            {
                "name": "Spring Security",
                "content": (
                    "Spring Security handles the two related but distinct concerns of authentication (who is "
                    "this user, really?) and authorization (what is this authenticated user allowed to do?). "
                    "It's built around a chain of servlet filters, each handling one specific concern - "
                    "extracting credentials, validating them, populating the security context, translating "
                    "security exceptions into proper HTTP responses - configured as a `SecurityFilterChain` "
                    "bean that runs before any request reaches your controllers. Traditional session-based "
                    "web applications rely on a server-side session (tied to a cookie) to remember an "
                    "authenticated user across requests; stateless REST APIs instead typically authenticate "
                    "every single request independently via a bearer token (commonly a JWT) sent in the "
                    "Authorization header, validated by a custom filter that populates the security context "
                    "fresh on each request with no server-side session at all.\n\n"
                    "Once a request is authenticated, authorization decisions can be enforced at two "
                    "levels: coarse-grained URL-pattern rules (`authorizeHttpRequests`, matching request "
                    "paths to required roles/authorities early in the filter chain) or fine-grained "
                    "method-level checks (`@PreAuthorize` with a SpEL expression, evaluated closer to the "
                    "actual business logic, which can reference method arguments for checks like \"the "
                    "current user must own this specific record\"). CSRF (Cross-Site Request Forgery) "
                    "protection is another recurring topic: it defends against a browser automatically "
                    "attaching a valid session cookie to a forged request from a malicious site, a real risk "
                    "for cookie-based session auth, but typically irrelevant (and disabled) for token-based "
                    "APIs where the token must be explicitly attached by the client and isn't auto-included "
                    "by the browser the way a cookie is."
                ),
                "questions": [
                    ("easy", "What is the difference between authentication and authorization?",
                     "Authentication verifies who the user is (e.g. validating a username/password or a JWT signature). Authorization determines what an authenticated user is allowed to do (e.g. checking if they have the \"ADMIN\" role). Spring Security handles both, authentication first, then authorization decisions based on the resulting Authentication object's granted authorities."),
                    ("medium", "What is a SecurityFilterChain, and what role do filters play?",
                     "Spring Security is built around a chain of Servlet filters, each handling one concern (form login, basic auth, exception translation, authorization). A SecurityFilterChain is a configured sequence of these filters applied to matching requests before they reach your controllers, configured via a SecurityFilterChain @Bean in modern Spring Security."),
                    ("medium", "How would you secure a stateless REST API with JWTs, at a high level?",
                     "Disable session creation (stateless policy) since there's no server-side session to maintain. Add a custom filter (extending OncePerRequestFilter) placed before the standard authentication filter that extracts the JWT from the Authorization header, validates its signature and expiry, and populates the SecurityContext with an Authentication object built from the token's claims - so later authorization checks see an authenticated user with no session lookup."),
                    ("hard", "What is CSRF, and why is it typically disabled for stateless REST APIs but not traditional web apps?",
                     "CSRF tricks a logged-in user's browser into submitting an unwanted request to a site where they're authenticated, exploiting the browser's automatic inclusion of cookies. It's a real risk for cookie/session-based auth. For stateless APIs authenticated via a bearer token in an explicit header (not auto-attached by the browser), the attack vector doesn't apply the same way, so CSRF protection is typically disabled there - but should stay enabled for cookie-based session auth."),
                    ("hard", "What's the difference between method-level security (@PreAuthorize) and URL-based configuration?",
                     "URL-based configuration (authorizeHttpRequests) applies coarse-grained rules based on request path patterns, evaluated early in the filter chain. Method-level security (@PreAuthorize, enabled via @EnableMethodSecurity) allows fine-grained, expression-based checks closer to the business logic, including checks based on method arguments (e.g. \"the current user must own this record\"), which URL patterns alone can't express."),
                    ("easy", "What does PasswordEncoder do, and why should passwords never be stored in plaintext?",
                     "PasswordEncoder (typically BCryptPasswordEncoder) hashes a password with a computationally expensive, salted algorithm before storing it, and verifies a login attempt by hashing the supplied password and comparing, never by decrypting a stored value (a proper hash isn't reversible at all). Storing plaintext passwords means a single database breach exposes every user's real password directly, which - given password reuse across sites - endangers users well beyond just your application."),
                    ("medium", "What is the SecurityContext, and how does it relate to the currently authenticated user?",
                     "SecurityContext holds the Authentication object representing the currently authenticated principal for the current thread, accessible anywhere in that request's processing via SecurityContextHolder.getContext().getAuthentication() - this is how a controller or service method can find out \"who is making this request\" without it being explicitly passed as a parameter through every layer."),
                    ("hard", "What is the difference between roles and authorities in Spring Security?",
                     "An authority is any granted permission string (e.g. \"READ_REPORTS\"). A role is a specific, conventionally-named authority prefixed with \"ROLE_\" (e.g. \"ROLE_ADMIN\") that Spring Security's role-based helper methods (hasRole(\"ADMIN\")) automatically add the prefix for. Authorities are the more general, finer-grained mechanism; roles are really just a naming convention layered on top for the common case of broad user categories rather than individual permissions."),
                ],
            },
            {
                "name": "Configuration & Profiles",
                "content": (
                    "Externalizing configuration - rather than hardcoding values in Java - is central to "
                    "building an application that behaves correctly across different environments (local "
                    "dev, CI, staging, production) without code changes. `application.properties` (or the "
                    "YAML equivalent, `application.yml`) is Spring Boot's default externalized config file, "
                    "and many of its keys bind directly to auto-configured beans (`server.port`, "
                    "`spring.datasource.url`) with zero extra code needed. For your own custom settings, "
                    "`@Value(\"${some.property}\")` injects a single value into a field, while "
                    "`@ConfigurationProperties` binds a whole related group of hierarchical properties onto a "
                    "strongly-typed POJO in one shot - generally the better choice once you have more than a "
                    "handful of related settings, since it's more maintainable and supports validation "
                    "annotations directly on the bound fields.\n\n"
                    "Spring profiles let you activate environment-specific configuration and beans: an "
                    "`application-dev.properties` file overlays (and can override) the base "
                    "`application.properties` when the \"dev\" profile is active, and a bean or component "
                    "annotated `@Profile(\"dev\")` is only registered when that profile is active - commonly "
                    "used to swap a real external integration (a payment gateway, an email sender) for a "
                    "local mock/no-op implementation outside production. Understanding property resolution "
                    "*order* matters in practice: command-line arguments and environment variables generally "
                    "take precedence over profile-specific files, which take precedence over the base "
                    "`application.properties` - a common real-world debugging scenario is \"why isn't my "
                    "properties file change taking effect,\" which often turns out to be an environment "
                    "variable silently overriding it at a higher precedence level. Real secrets (API keys, "
                    "database passwords) should never be committed in a properties file at all - environment "
                    "variables or a dedicated secrets manager are the standard approaches."
                ),
                "questions": [
                    ("easy", "What is the purpose of application.properties/application.yml?",
                     "It's the default externalized configuration file for application-wide settings - server port, database connection details, logging levels, custom properties - without hardcoding them in Java code, with many settings automatically bound to auto-configured beans."),
                    ("medium", "What is the difference between @Value and @ConfigurationProperties?",
                     "@Value injects a single property value directly into a field. @ConfigurationProperties binds a whole group of related, hierarchical properties onto a strongly-typed POJO in one go, which is more maintainable, supports validation, and works better for structured/nested configuration than repeating @Value on many fields."),
                    ("medium", "What are Spring profiles, and what are they used for?",
                     "Profiles let you define environment-specific beans and configuration (\"dev\", \"test\", \"prod\") only active when that profile is enabled (spring.profiles.active). application-dev.properties can override the base file, or a @Bean/@Component annotated @Profile(\"dev\") is only registered in that environment - commonly used to swap a real payment gateway for a mock in tests."),
                    ("hard", "What is the property resolution order in Spring Boot when the same property is set in multiple places?",
                     "Roughly, highest to lowest precedence: command-line arguments, JVM system properties, OS environment variables, profile-specific application-{profile}.properties, the base application.properties, then @PropertySource files and code defaults. Understanding this matters for debugging \"why isn't my property taking effect\" - an env var can silently override application.yml."),
                    ("hard", "How would you externalize secrets safely instead of hardcoding them in application.properties?",
                     "Common approaches: environment variables (referenced as `${DB_PASSWORD}`) so the value never lives in version control; a dedicated secrets manager (Vault, AWS Secrets Manager) integrated via Spring Cloud Config or a custom PropertySource; or, for local dev only, a gitignored application-local.properties. The core principle is that real secrets never get committed to source control."),
                    ("easy", "What is the difference between application.properties and application.yml format-wise, and can you use both?",
                     "They configure exactly the same underlying properties, just in different syntax - .properties uses flat dot-separated keys (spring.datasource.url=...), while .yml uses nested indentation (spring:\\n  datasource:\\n    url: ...), which is often more readable for deeply nested configuration. You generally pick one format per application rather than mixing both for the same environment, since having both active risks confusing precedence between them."),
                    ("medium", "What is a default profile, and what happens if no profile is explicitly activated?",
                     "If no profile is set via spring.profiles.active, Spring Boot uses the implicit \"default\" profile, which just means only the base application.properties (with no profile-specific suffix) applies - any @Profile(\"dev\")-annotated bean would not be registered in that case, since \"default\" doesn't match \"dev\" unless a bean is explicitly annotated @Profile(\"default\") too."),
                    ("hard", "How do relaxed binding rules affect how environment variables map to Spring configuration properties?",
                     "Spring Boot's relaxed binding lets an environment variable like SPRING_DATASOURCE_URL (uppercase, underscore-separated, since many shells/containers don't support dots or lowercase keys well) automatically bind to the property spring.datasource.url without any special mapping configuration - Spring normalizes case, dashes, and underscores when matching environment variables and properties files to the same canonical property name, which is exactly what makes Spring Boot config portable to container/cloud environments where env vars are the natural configuration channel."),
                ],
            },
            {
                "name": "Testing",
                "content": (
                    "Testing a Spring Boot application well means matching the *weight* of your test to what "
                    "it actually needs to verify, rather than defaulting to the heaviest option everywhere. "
                    "A plain unit test with no Spring context at all - a real object under test, with its "
                    "dependencies replaced by hand-built mocks (typically via Mockito) - is the fastest and "
                    "should form the bulk of a healthy test suite, since it verifies business logic in total "
                    "isolation with no framework startup cost. `@SpringBootTest` sits at the other extreme: it "
                    "loads the full (or a broad slice of the) application context, letting you write genuine "
                    "integration tests that exercise real bean wiring, real auto-configuration, and how "
                    "components actually collaborate - valuable, but slow enough that overusing it makes a "
                    "test suite sluggish and brittle.\n\n"
                    "Between those extremes, Spring Boot's test slices load only the portion of the context "
                    "relevant to one architectural layer: `@WebMvcTest` loads just the web layer (with "
                    "`MockMvc` available to simulate HTTP requests against controllers without a running "
                    "server), and `@DataJpaTest` loads just the persistence layer (repositories, an "
                    "auto-configured in-memory or test database, each test wrapped in a transaction rolled "
                    "back afterward so tests don't pollute each other). `@MockBean` lets you replace one "
                    "specific bean in a loaded context with a Mockito mock, useful for isolating the class "
                    "under test from one particular external dependency (a third-party API client) while "
                    "still exercising real Spring wiring around it. Getting the unit/slice/full-integration "
                    "balance right - lots of fast unit tests, a moderate number of focused slice tests, a "
                    "small number of true end-to-end integration tests - is what keeps a growing test suite "
                    "both trustworthy and fast."
                ),
                "questions": [
                    ("easy", "What does @SpringBootTest do, and when would you use it vs a plain unit test?",
                     "@SpringBootTest loads the full (or a sliced) Spring application context, allowing integration-style tests that exercise real bean wiring and configuration. It's heavier and slower than a plain unit test with mocked dependencies, so it's best reserved for genuine integration tests, not simple business logic in isolation."),
                    ("medium", "What is the purpose of @MockBean in a Spring Boot test?",
                     "@MockBean replaces a bean in the Spring application context with a Mockito mock for the test, letting you isolate the class under test from a real dependency (an external API client, a repository) while still loading a (partial) Spring context - useful when you want Spring wiring but control over a specific collaborator's behavior."),
                    ("medium", "What is MockMvc used for in Spring Boot testing?",
                     "MockMvc lets you test the web layer (controllers, request mapping, serialization, status codes, validation) by simulating HTTP requests against your controllers without starting a real embedded server - faster than a full end-to-end test, while still exercising the real DispatcherServlet-based pipeline."),
                    ("hard", "What's the difference between @DataJpaTest and @SpringBootTest for the persistence layer?",
                     "@DataJpaTest loads only the JPA-related slice of the context (repositories, EntityManager, an auto-configured test database by default), faster and more focused - each test runs in its own transaction rolled back afterward. A full @SpringBootTest loads everything, slower, appropriate only when you genuinely need the whole application wired up."),
                    ("hard", "What testing pyramid tradeoffs matter when deciding unit vs integration test balance?",
                     "Plain unit tests (no Spring context) are fast and cheap, forming the bulk of the suite, testing business logic in isolation with mocked dependencies. @SpringBootTest integration tests are slow and should be used sparingly to verify the pieces actually wire together. Over-relying on heavy integration tests makes the suite slow and brittle; under-testing integration leaves you exposed to configuration/wiring bugs unit tests can't catch."),
                    ("easy", "What is the difference between @Mock and @MockBean?",
                     "@Mock (plain Mockito) creates a mock object for use in a plain unit test with no Spring context involved at all - fast, no framework overhead. @MockBean is Spring Boot's own annotation that creates a Mockito mock AND registers it into the Spring application context in place of the real bean, only meaningful in a test that actually loads a Spring context (like @SpringBootTest or @WebMvcTest)."),
                    ("medium", "What does @Transactional on a test method do, and why is it useful for database tests?",
                     "It wraps the test method in a transaction that's automatically rolled back after the test finishes, regardless of outcome - so a test can freely insert/modify/delete data without needing manual cleanup and without one test's data leaking into the next test's run, keeping database-touching tests independent and repeatable."),
                    ("hard", "What is Testcontainers, and why might you prefer it over an in-memory database like H2 for integration tests?",
                     "Testcontainers spins up real Docker containers (a real PostgreSQL, a real Redis) for the duration of a test run, rather than substituting an in-memory approximation. This matters because an in-memory database like H2 doesn't perfectly replicate your real production database's SQL dialect, constraints, or feature set - a query that passes against H2 in tests can still fail against the real Postgres in production. Testcontainers trades some test startup speed for testing against the actual technology you'll deploy with."),
                ],
            },
        ],
    },
    {
        "topic": "RAG",
        "short_label": "RAG",
        "category": "AI/LLM",
        "subtopics": [
            {
                "name": "Core Concepts",
                "content": (
                    "Retrieval-Augmented Generation (RAG) combines two previously separate techniques: "
                    "information retrieval (finding relevant documents/passages for a query) and text "
                    "generation (an LLM producing fluent natural-language output). Instead of relying purely "
                    "on what an LLM memorized during training, RAG retrieves relevant external content at "
                    "query time and feeds it into the model's context window alongside the question, "
                    "grounding the generated answer in real, current, and specific source material. This "
                    "matters for three practical reasons: it lets a model answer accurately about information "
                    "that postdates its training cutoff or was never in its training data at all (private "
                    "company documents, for instance); it reduces (though doesn't eliminate) hallucination, "
                    "since the model has real supporting text to draw from instead of confabulating from an "
                    "imprecise memory of training data; and it lets you update the knowledge a system can "
                    "draw on simply by re-indexing documents, without the cost and complexity of retraining "
                    "the underlying model.\n\n"
                    "A typical RAG pipeline splits into two stages running at very different times: an "
                    "offline indexing stage, done once (or periodically as documents change), where source "
                    "documents are split into chunks, each chunk is embedded into a vector representation, "
                    "and those vectors are stored in a vector database; and an online query stage, run for "
                    "every user request, where the incoming query is embedded the same way, the most similar "
                    "stored chunks are retrieved, and both the query and the retrieved chunks are assembled "
                    "into a prompt for the LLM to generate a grounded final answer from. Nearly every "
                    "practical RAG challenge - poor answers, missed context, hallucination despite retrieval "
                    "- traces back to a failure in one of these two stages, which is why understanding them "
                    "as genuinely separate concerns (with separate evaluation) is the foundation for everything "
                    "else in RAG."
                ),
                "questions": [
                    ("easy", "What is RAG, and why is it used instead of relying purely on an LLM's built-in knowledge?",
                     "RAG (Retrieval-Augmented Generation) combines a retrieval step (fetching relevant external documents/chunks based on the query) with a generation step (an LLM producing an answer grounded in those retrieved documents). It lets a model answer accurately about information outside its training data or cutoff, reduces hallucination by grounding answers in real source material, and allows updating the knowledge base without retraining the model."),
                    ("easy", "What are the two main stages of a typical RAG pipeline?",
                     "An indexing stage (offline, done once/periodically): documents are chunked, embedded into vectors, and stored in a vector store. A query/retrieval stage (online, per request): the query is embedded, the most similar chunks are retrieved, and both the query and retrieved chunks are passed to the LLM to generate a grounded answer."),
                    ("medium", "What is \"grounding\" in RAG, and why does it help reduce hallucination?",
                     "Grounding means constraining the LLM's answer to be based on specific retrieved source material in its context window, rather than solely its trained-in knowledge. It helps because the model can quote/paraphrase actual retrieved text instead of confabulating from imprecise training memory - though it doesn't eliminate hallucination entirely, since a model can still misread or embellish beyond what's actually supported."),
                    ("medium", "What's the difference between RAG and fine-tuning for adapting an LLM to a domain?",
                     "Fine-tuning updates the model's weights on domain-specific data - good for teaching style or deeply ingrained behavior, but expensive, requires retraining to update knowledge, and doesn't reliably teach new facts. RAG doesn't touch model weights - it supplies fresh information at inference time via retrieval, is cheaper to keep current (just re-index), and provides traceable sources, but is limited by retrieval quality and context window size."),
                    ("hard", "What are the main failure modes of a RAG system, beyond \"the LLM hallucinates\"?",
                     "Retrieval failure (the relevant chunk simply wasn't retrieved); chunking issues (a relevant fact split across chunk boundaries, so no single chunk has the full answer); context overload (too many/irrelevant chunks dilute the useful signal or exceed the context window); embedding mismatch (query and document phrase things differently enough their embeddings aren't close); and stale or contradictory retrieved documents."),
                    ("easy", "What does it mean for RAG output to be \"traceable\" or \"cite its sources\"?",
                     "Because RAG retrieves specific chunks from known source documents before generating an answer, the system can attach metadata about exactly which chunk(s)/document(s) informed a given answer, letting the answer link back to (or quote) its actual sources. This is something a purely parametric LLM (no retrieval) fundamentally can't offer, since its \"knowledge\" is baked into weights with no record of which specific training document a given fact came from."),
                    ("medium", "Why might a RAG system still hallucinate even when retrieval works correctly?",
                     "Even with the right chunks retrieved, the LLM can still misread the retrieved text, over-generalize beyond what it actually says, fill in gaps with its own (possibly wrong) prior knowledge when the retrieved context is incomplete, or simply ignore the provided context if the prompt doesn't instruct it strongly enough to stay grounded. Good retrieval is necessary but not sufficient - generation-side prompting and evaluation (like faithfulness checks) still matter."),
                    ("hard", "In what scenarios is RAG a poor fit compared to fine-tuning or simply using a larger context window?",
                     "RAG adds real latency and engineering complexity (indexing pipeline, vector store, retrieval tuning) that isn't worth it for small, static knowledge bases that fit comfortably in a model's context window - just including everything directly in the prompt (long-context stuffing) can be simpler and more reliable there. RAG is also a poor fit when the task is really about style/format/behavior rather than factual knowledge (fine-tuning suits that better), or when sub-second latency is critical and even a fast retrieval step is too much overhead."),
                ],
            },
            {
                "name": "Embeddings & Vector Stores",
                "content": (
                    "An embedding is a dense numerical vector representation of a piece of text, produced by "
                    "an embedding model trained so that texts with similar meaning end up positioned close "
                    "together in that high-dimensional vector space, regardless of exact wording overlap. "
                    "This is what makes semantic retrieval possible: embedding a user's query and finding the "
                    "nearest document embeddings surfaces conceptually relevant content even when the query "
                    "and the source document phrase the same idea in completely different words - something "
                    "exact keyword matching can't do. Similarity between two embeddings is most commonly "
                    "measured with cosine similarity (the angle between the vectors, ignoring magnitude), "
                    "which tends to capture semantic closeness for text better than a magnitude-sensitive "
                    "metric like Euclidean distance.\n\n"
                    "A vector database (or vector store) persists these embeddings alongside metadata about "
                    "their source, and - crucially - provides efficient approximate nearest-neighbor (ANN) "
                    "search, since brute-force comparison against every stored vector doesn't scale once "
                    "you're indexing millions of chunks. Most production vector stores use a graph-based "
                    "indexing structure like HNSW (Hierarchical Navigable Small World), which builds "
                    "multiple layers of proximity graphs - sparse at the top for fast coarse navigation, "
                    "dense at the bottom for precise local search - trading a small amount of exactness for a "
                    "large gain in search speed. Pure dense-embedding retrieval isn't always ideal on its own: "
                    "it can miss exact-match needs (a specific error code, a product SKU, a rare technical "
                    "term) that a traditional sparse/keyword method like BM25 handles naturally, which is why "
                    "many real systems combine dense and sparse retrieval (hybrid search) and merge the two "
                    "result sets, often via reciprocal rank fusion, rather than relying on embeddings alone."
                ),
                "questions": [
                    ("easy", "What is a vector embedding, and why are they used for retrieval?",
                     "An embedding is a dense numerical vector representation of text produced by an embedding model, positioned such that semantically similar texts have vectors that are close together by some distance metric. Embedding a query and finding the nearest document embeddings captures semantic relevance rather than requiring exact keyword matches."),
                    ("medium", "What's the difference between cosine similarity and Euclidean distance for embeddings?",
                     "Cosine similarity measures the angle between two vectors, ignoring magnitude - it captures directional/semantic similarity regardless of length, making it the common choice for text embeddings. Euclidean distance measures straight-line distance and is sensitive to magnitude, useful when magnitude itself is meaningful, but for most normalized text-embedding use cases cosine similarity is preferred."),
                    ("medium", "What is a vector database, and what capability does it add beyond a plain list of embeddings?",
                     "A vector store persists embeddings with source metadata and provides efficient approximate nearest-neighbor (ANN) search - critical because brute-force comparison against every stored vector doesn't scale. Vector stores use indexing structures (like HNSW) to make similarity search fast across millions of vectors, at a small cost in exactness."),
                    ("hard", "What is HNSW, and why is it commonly used in vector databases?",
                     "HNSW (Hierarchical Navigable Small World) is a graph-based approximate nearest-neighbor algorithm building multiple layers of proximity graphs - sparser at higher layers for fast coarse navigation, denser at lower layers for fine-grained search. It offers a strong speed/accuracy tradeoff and supports incremental insertion without a full rebuild."),
                    ("hard", "Why might you choose hybrid (sparse + dense) retrieval instead of pure embedding-based retrieval?",
                     "Dense embedding retrieval excels at semantic matches but can miss exact keyword, code identifier, or rare-term matches that a sparse method like BM25 handles well (rewarding exact term overlap weighted by rarity). Combining both (often via reciprocal rank fusion) captures semantic relevance and exact-match precision, especially important in domains with jargon or IDs that embeddings alone might blur together."),
                    ("easy", "What is embedding dimensionality, and does a higher dimension always mean better retrieval?",
                     "Dimensionality is the length of the vector an embedding model outputs (e.g. 768, 1536, 3072). Higher dimensionality can capture more nuance but isn't automatically better - it increases storage size and search cost, and beyond a certain point returns diminishing (or even negative, due to the curse of dimensionality affecting distance metrics) improvements in retrieval quality. The right dimensionality is usually whatever the chosen embedding model was trained to output, not something tuned independently."),
                    ("medium", "Why must the same embedding model be used for both indexing documents and embedding queries at search time?",
                     "Different embedding models place text in entirely different, incompatible vector spaces - even if both are good models individually, a query embedded with Model A compared against documents embedded with Model B produces meaningless similarity scores, since the two vector spaces have no shared geometry. Consistency (same model, same version, same preprocessing) between indexing and querying is a strict requirement, not an optimization."),
                    ("hard", "What is quantization in the context of vector stores, and what tradeoff does it involve?",
                     "Quantization compresses embedding vectors (e.g. from 32-bit floats to 8-bit integers, or further to binary) to reduce memory footprint and speed up distance calculations, which matters enormously at scale (millions to billions of vectors). The tradeoff is a small loss of precision in similarity scores/ranking accuracy in exchange for large gains in memory usage and query speed - often re-ranking a small quantized-search candidate set with the original full-precision vectors gets back most of the accuracy while keeping most of the speed benefit."),
                ],
            },
            {
                "name": "Chunking Strategies",
                "content": (
                    "Chunking - splitting source documents into smaller pieces before embedding - exists "
                    "because embedding models have hard input-length limits, and even well within that "
                    "limit, cramming a very long document into a single embedding vector averages out and "
                    "dilutes its specific details, making retrieval far less precise than it would be with "
                    "smaller, more focused chunks. Chunk size is fundamentally a tradeoff: smaller chunks give "
                    "more precise, targeted retrieval and let more distinct pieces of information fit within "
                    "the LLM's context window at generation time, but risk losing surrounding context and "
                    "can split a single coherent answer across multiple chunk boundaries; larger chunks "
                    "preserve more surrounding context per chunk but dilute embedding specificity and consume "
                    "more of the context budget per chunk retrieved.\n\n"
                    "Chunk overlap - letting consecutive chunks share a bit of text at their boundary rather "
                    "than cutting with zero repetition - is a common mitigation for the boundary-splitting "
                    "problem, at the cost of some redundant storage. Beyond simple fixed-size splitting "
                    "(cutting every N tokens/characters regardless of content), more sophisticated approaches "
                    "exist: semantic chunking splits at natural topic boundaries by embedding consecutive "
                    "sentences and cutting where similarity between them drops significantly, producing more "
                    "thematically coherent chunks at the cost of extra preprocessing; and structure-aware "
                    "chunking respects a document's actual layout (headers, tables, code blocks), avoiding "
                    "the naive failure of splitting a table mid-row or separating a code block from the "
                    "explanation right above it, often keeping structural metadata (like the enclosing "
                    "heading path) attached to each chunk for extra retrieval and generation context even if "
                    "that text itself isn't repeated inside the chunk."
                ),
                "questions": [
                    ("easy", "Why do documents need to be split into chunks before embedding?",
                     "Embedding models have a maximum input length, and even within that limit, embedding a very long document into one vector dilutes and averages out its specific details, making retrieval less precise. Smaller, focused chunks let each embedding represent a more specific, retrievable unit of meaning."),
                    ("medium", "What is chunk overlap, and why is it used?",
                     "Chunk overlap means consecutive chunks share some text at their boundary instead of cutting cleanly with no repetition. This prevents a fact or sentence spanning a chunk boundary from being split so neither chunk contains the complete idea, at the cost of some redundant storage/embedding."),
                    ("medium", "What's the tradeoff between small chunks and large chunks?",
                     "Small chunks give more precise, targeted retrieval and let you fit more distinct chunks into the context window, but risk losing surrounding context and can split an answer's information across chunks. Large chunks preserve more context per chunk but dilute embedding specificity and use more of the context window per chunk, letting in fewer total chunks."),
                    ("hard", "What is semantic chunking, and how does it differ from fixed-size chunking?",
                     "Fixed-size chunking splits text into chunks of a set token/character count regardless of content structure. Semantic chunking tries to split at natural topic boundaries - e.g. embedding consecutive sentences and splitting where similarity between adjacent sentences drops significantly - keeping each chunk more thematically coherent, at the cost of extra preprocessing and variable chunk sizes."),
                    ("hard", "How does document structure (headers, tables, code blocks) complicate chunking?",
                     "Naively splitting by fixed character count can break a table mid-row or separate a code block from its explanation, hurting retrieval and comprehension. Structure-aware chunking parses the document's actual layout and chunks along natural boundaries, often keeping metadata (like \"this chunk is under heading X > Y\") attached to each chunk for extra context even if the heading text isn't in the chunk itself."),
                    ("easy", "What is a reasonable starting chunk size, and why isn't there one universally correct answer?",
                     "A common starting point is a few hundred tokens (e.g. 200-500) with 10-20% overlap, but the right size genuinely depends on the content (dense technical text needs different sizing than conversational transcripts), the embedding model's own effective range, and how the retrieved chunks will be used downstream - there's no universal answer, which is why chunk size is usually tuned empirically against a real evaluation set rather than fixed a priori."),
                    ("medium", "What is recursive chunking, and why is it often preferred over a naive fixed-character split?",
                     "Recursive chunking tries a prioritized list of separators - paragraph breaks first, then sentence breaks, then word breaks - only falling back to a harder cut if a chunk is still too large after trying the more natural separators. This produces chunks that respect natural language boundaries far more often than blindly cutting at a fixed character count, which can otherwise slice a sentence or word in half."),
                    ("hard", "How would you decide whether to re-chunk an entire corpus versus only incrementally chunking new/changed documents?",
                     "A full re-chunk is simplest and guarantees consistency but is expensive and wasteful for large, mostly-stable corpora, and briefly stales the index during the rebuild. Incremental chunking (only processing documents that are new, changed, or deleted since the last run, typically tracked via a content hash or a change-data-capture feed) scales far better for large, frequently-updated corpora, but requires more engineering to track document identity and correctly purge stale chunks from removed/changed documents - the right choice depends mostly on corpus size and how often it actually changes."),
                ],
            },
            {
                "name": "Retrieval Techniques",
                "content": (
                    "Basic vector similarity search - embed the query, return the top-k nearest document "
                    "embeddings - is the starting point for retrieval, but real systems layer several "
                    "additional techniques on top to improve result quality. Re-ranking follows a "
                    "\"retrieve cheaply, rank precisely\" pattern: an initial, cheap retrieval pass pulls a "
                    "larger candidate set (say, the top 50 by vector similarity), and a more expensive, more "
                    "accurate model - often a cross-encoder that processes the query and each candidate "
                    "document jointly, rather than comparing pre-computed independent embeddings - re-scores "
                    "and reorders that smaller set to produce a better-ranked final top-k, balancing overall "
                    "speed against per-result accuracy. Maximal Marginal Relevance (MMR) addresses a "
                    "different problem: pure top-k-by-similarity results are often near-duplicates of each "
                    "other (several chunks all making basically the same point), wasting context window "
                    "space that could otherwise cover a broader spread of relevant information - MMR "
                    "explicitly balances relevance to the query against diversity relative to already-chosen "
                    "results.\n\n"
                    "Query expansion/rewriting addresses the vocabulary gap between how users phrase "
                    "questions and how source documents state the same facts: rephrasing the query, "
                    "generating multiple query variants, or even generating a hypothetical answer to the "
                    "query and embedding *that* instead of the raw query (HyDE - Hypothetical Document "
                    "Embeddings) can retrieve better matches than embedding the literal user question. And "
                    "single-hop retrieval - one retrieval pass, then generate - isn't sufficient for every "
                    "question: some questions genuinely require combining information found across multiple, "
                    "separately-retrieved documents (find a company's competitors, then each competitor's "
                    "founding date), which needs multi-hop retrieval - iterative rounds of retrieval "
                    "interleaved with intermediate reasoning that generates the next round's follow-up "
                    "queries based on what's been found so far."
                ),
                "questions": [
                    ("easy", "What is semantic search, and how does it differ from keyword search?",
                     "Keyword search matches documents based on literal presence/frequency of exact query terms. Semantic search embeds both query and documents into vector space and retrieves by similarity, finding relevant results even with different wording (synonyms, paraphrasing) - at the cost of potentially missing an exact rare-term match a keyword search would catch trivially."),
                    ("medium", "What is re-ranking in a RAG pipeline, and why add it after initial retrieval?",
                     "Re-ranking takes the initial candidates (retrieved cheaply, e.g. top 50 by vector similarity) and re-scores them with a more expensive, more accurate model (often a cross-encoder processing query and document jointly) to produce a better-ordered final top-k. It's a \"retrieve cheaply, rank precisely\" pattern balancing speed and accuracy."),
                    ("medium", "What is Maximal Marginal Relevance (MMR), and what problem does it address?",
                     "MMR selects results by balancing relevance to the query against diversity relative to already-selected results, rather than just picking the top-k most similar chunks. This addresses the top results by pure similarity often being near-duplicates of each other, wasting context window space instead of providing a broader, more useful spread of information."),
                    ("hard", "What is query expansion/rewriting, and why might it improve retrieval quality?",
                     "It transforms the user's original query (which may be short, ambiguous, or phrased differently from the source documents) into improved queries before retrieval - rephrasing, generating variants, or even generating a hypothetical answer and embedding that instead (HyDE). This bridges the vocabulary/phrasing gap between how users ask and how documents state facts."),
                    ("hard", "What's the difference between single-hop and multi-hop retrieval?",
                     "Single-hop retrieval does one retrieval pass and generates an answer - sufficient when the answer exists in a single chunk. Multi-hop retrieval is needed when answering requires combining information across multiple, separately-retrieved documents (e.g. first find who a company's competitors are, then each one's founding date) - implemented via iterative retrieval with intermediate reasoning generating follow-up queries."),
                    ("easy", "What does \"top-k\" mean in the context of retrieval?",
                     "Top-k refers to retrieving the k highest-scoring (most similar, or best-ranked after re-ranking) chunks for a given query, where k is a chosen number (commonly somewhere between 3 and 10 in practice). It's the mechanism for deciding how much retrieved content actually gets passed into the LLM's context window for a given query."),
                    ("medium", "What is a cross-encoder, and how does it differ from the bi-encoder used for initial embedding-based retrieval?",
                     "A bi-encoder (used for initial retrieval) embeds the query and each document independently into fixed vectors ahead of time, then compares them via a cheap similarity calculation - fast enough to search millions of documents, but each embedding is computed with no knowledge of the other side of the comparison. A cross-encoder processes the query and a specific document together in a single forward pass, letting it model fine-grained interactions between them for much more accurate relevance scoring - but it's too slow to run against every document in a large corpus, which is exactly why it's used only to re-rank a bi-encoder's smaller candidate set, not for initial retrieval."),
                    ("hard", "What is reciprocal rank fusion, and when is it used?",
                     "Reciprocal rank fusion is a method for combining multiple ranked result lists (e.g. a dense-embedding search's ranking and a sparse BM25 search's ranking) into a single merged ranking, scoring each document by the sum of 1/(k + rank) across the lists it appears in, rather than needing the different lists' raw scores to be on a comparable scale. It's the standard technique for combining hybrid dense+sparse retrieval results, since dense similarity scores and BM25 scores aren't otherwise directly comparable."),
                ],
            },
            {
                "name": "RAG Architecture & Pipeline",
                "content": (
                    "Beyond the core retrieve-then-generate mechanism, several architectural decisions "
                    "determine how well a RAG system performs in practice. The prompt template assembling "
                    "retrieved chunks, the user's query, and system instructions materially affects grounding "
                    "quality - explicit instructions like \"answer only using the provided context, and say "
                    "so if the answer isn't present\" push the model toward relying on retrieved material "
                    "rather than falling back on its own possibly-outdated or hallucinated knowledge. "
                    "Metadata filtering narrows the search space using structured attributes attached to each "
                    "chunk (source, date, category, and critically, access permissions) applied before or "
                    "alongside the vector similarity search itself - essential for scenarios like multi-tenant "
                    "systems where a user must only ever retrieve chunks they're actually authorized to see, "
                    "something pure semantic similarity has no concept of enforcing on its own.\n\n"
                    "Choosing top-k (how many chunks to retrieve and pass along) is an empirically-tuned "
                    "balance: too few risks missing genuinely relevant information, too many adds irrelevant "
                    "or distracting content that can measurably degrade an LLM's ability to use the "
                    "genuinely relevant information buried among it (worse than just wasting context budget - "
                    "it can actively hurt answer quality). More advanced systems move beyond a single fixed "
                    "retrieve-then-generate pass entirely: agentic RAG lets the LLM's own reasoning decide "
                    "whether and what to retrieve during generation - issuing follow-up queries, reformulating "
                    "when initial context proves insufficient, or choosing between multiple available sources "
                    "- trading additional latency and cost for the ability to handle more complex, multi-step "
                    "information needs than a single static retrieval pass ever could. And because source "
                    "documents change over time, a production RAG system also needs an explicit strategy for "
                    "keeping its index current - full periodic re-indexing, incremental updates driven by "
                    "change detection, or a hybrid of both depending on how frequently different sources "
                    "actually change."
                ),
                "questions": [
                    ("easy", "What role does the prompt template play in a RAG system?",
                     "It defines how retrieved chunks, the user's query, and system instructions are assembled into the final LLM prompt - typically including instructions like \"answer only using the provided context\" and a clear structure separating context from question, which materially affects how well the model grounds its answer versus falling back on its own knowledge."),
                    ("medium", "What is the purpose of metadata filtering in a RAG retrieval pipeline?",
                     "Metadata filtering narrows the search space using structured attributes attached to each chunk (date, source, permissions, category) before or alongside vector similarity search - e.g. \"only search chunks the current user is authorized to see.\" This combines structured filtering precision with semantic search flexibility, essential for access control in multi-tenant RAG."),
                    ("medium", "How do you decide how many chunks (top-k) to retrieve and pass to the LLM?",
                     "It's a tradeoff: too few risks missing relevant information; too many increases irrelevant/distracting content, uses more context window and cost, and can degrade an LLM's ability to accurately use information buried mid-context. In practice, k is tuned empirically (often 3-10), sometimes combined with re-ranking to make a larger initial set more precise before truncating."),
                    ("hard", "What is agentic RAG, and how does it differ from a simple retrieve-then-generate pipeline?",
                     "Simple RAG does one fixed retrieve-then-generate pass. Agentic RAG lets the LLM decide during its own reasoning whether and what to retrieve - issuing multiple queries, reformulating if context is insufficient, choosing between sources, or interleaving retrieval with reasoning (similar to ReAct) - trading more latency/cost for handling more complex, multi-step information needs."),
                    ("hard", "How would you design a RAG system to keep its index up to date as source documents change?",
                     "Options: a full periodic re-index (simple but wasteful, with staleness windows); incremental indexing detecting changed/new/deleted documents (via a hash or change-data-capture feed) and re-embedding only those; or a hybrid where frequently-changing sources get near-real-time updates while stable sources re-index on a longer cadence. Deletion handling matters too - stale chunks from removed documents need active purging, not just being out-competed by newer results."),
                    ("easy", "What is the difference between the retrieval component and the generation component of a RAG system, in terms of what each is responsible for?",
                     "The retrieval component is responsible entirely for finding relevant source material - it never produces the final answer text itself. The generation component (the LLM) is responsible for synthesizing a coherent, natural-language answer from whatever it's given, but has no independent way to know what's actually relevant unless retrieval hands it the right material. Treating them as genuinely separate subsystems, each independently measurable and improvable, is key to diagnosing where a RAG system is actually underperforming."),
                    ("medium", "Why might you filter or deduplicate retrieved chunks before passing them into the prompt?",
                     "Multiple near-identical chunks (e.g. from overlapping chunking, or several documents restating the same fact) waste context window space on redundant information without adding retrieval value, and can also skew an LLM toward over-weighting a repeated point. Deduplicating or diversity-filtering (like MMR) before constructing the final prompt ensures the limited context budget is spent on genuinely distinct, useful information."),
                    ("hard", "What is the role of a system prompt versus the retrieved-context block in a RAG prompt template, and why keep them structurally separate?",
                     "The system prompt sets stable, query-independent behavior (tone, format, grounding instructions, refusal policy) that doesn't change per request. The retrieved-context block is dynamic content that changes every single query. Keeping them structurally and clearly separated (rather than interleaving instructions with retrieved text) makes the model less likely to confuse an instruction-like sentence that happens to appear inside a retrieved document with an actual system instruction - a real prompt-injection-adjacent risk when retrieved content comes from less-trusted sources."),
                ],
            },
            {
                "name": "Evaluation & Challenges",
                "content": (
                    "Evaluating a RAG system is genuinely harder than evaluating a classifier with clear "
                    "right/wrong labels, because the output is open-ended natural language with no single "
                    "\"correct answer\" string to match against - quality spans multiple, partially "
                    "independent dimensions (factual correctness, groundedness in the retrieved context vs. "
                    "hallucination, completeness, and simple relevance to what was actually asked), each "
                    "needing its own evaluation approach, often requiring either human judgment or an "
                    "LLM-as-judge rather than exact-match scoring. It's important to separate retrieval "
                    "evaluation from generation evaluation, since they're independent failure points: "
                    "retrieval evaluation asks \"did we fetch the right chunks?\" - measurable objectively "
                    "with precision/recall/MRR against a labeled set of query-to-relevant-document pairs, "
                    "with no LLM involved at all - while generation evaluation asks \"given the chunks we "
                    "did fetch, did the LLM produce a good answer from them?\", which is where "
                    "\"faithfulness\" (does the answer only claim things actually supported by the retrieved "
                    "context, rather than adding unsupported claims from the model's own knowledge) becomes a "
                    "central metric.\n\n"
                    "One well-documented, counterintuitive challenge is that simply having a larger context "
                    "window and stuffing in more retrieved chunks doesn't reliably fix quality problems: "
                    "research on \"lost in the middle\" shows even large-context models attend less reliably "
                    "to information placed in the middle of a long context compared to the beginning or end, "
                    "so retrieval *precision* (fetching fewer, more relevant chunks) often matters more for "
                    "real answer quality than raw retrieval *recall* or context capacity. Building a real "
                    "evaluation pipeline for production RAG typically means maintaining a labeled test set of "
                    "representative queries with known-relevant documents and expected answer characteristics, "
                    "running both retrieval and generation evaluation automatically against every meaningful "
                    "pipeline change, and gating deployments on measurable regressions - the same discipline "
                    "you'd expect from evaluating any other machine learning system before it ships, adapted "
                    "to RAG's specific, harder-to-pin-down failure modes."
                ),
                "questions": [
                    ("easy", "Why is evaluating a RAG system harder than a classifier with clear right/wrong labels?",
                     "RAG output is open-ended natural language, so there's no single exact \"correct answer\" to match against - quality depends on multiple dimensions (factual correctness, groundedness vs. hallucination, completeness, relevance) that each need their own evaluation approach, often requiring human judgment or an LLM-as-judge rather than simple string matching."),
                    ("medium", "What's the difference between evaluating retrieval quality and generation quality?",
                     "Retrieval evaluation asks \"did we fetch the right chunks?\" - measured with precision/recall/MRR against labeled query-to-relevant-document pairs, independent of the LLM. Generation evaluation asks \"given the retrieved chunks, did the LLM produce a good answer?\" Both need separate evaluation since a bad final answer could stem from either failure independently."),
                    ("medium", "What does \"faithfulness\" mean as a RAG evaluation metric?",
                     "Faithfulness measures whether the generated answer's claims are actually supported by the retrieved context, as opposed to adding unsupported information from the model's own knowledge (hallucination even with good retrieval). Typically evaluated by checking whether each claim traces back to something in the retrieved chunks, often automated via LLM-as-judge."),
                    ("hard", "What is context window saturation, and how does it hurt RAG quality even with large-context models?",
                     "Even large-context models attend less reliably to information placed in the middle of a long context (\"lost in the middle\") compared to the beginning or end - so stuffing more chunks into a bigger window doesn't guarantee the model uses the relevant ones well if buried among many others. This is why retrieval precision often matters more than raw context capacity."),
                    ("hard", "How would you set up an automated evaluation pipeline for a RAG system in production, conceptually?",
                     "Maintain a labeled test set of representative queries with known-relevant documents/expected answer characteristics. Run retrieval evaluation (precision/recall against labeled relevant chunks) and generation evaluation (LLM-as-judge scoring faithfulness, relevance, completeness) on every meaningful pipeline change. Track metrics over time and gate deployments on regressions, similar to gating a traditional ML model on accuracy before shipping."),
                    ("easy", "What is Mean Reciprocal Rank (MRR), as a retrieval evaluation metric?",
                     "MRR measures, across a set of test queries, the average of 1/rank of the first genuinely relevant result for each query - if the first relevant chunk is ranked #1, that query contributes 1.0; if it's ranked #4, it contributes 0.25. It specifically rewards surfacing a relevant result as early as possible in the ranked list, which matters a lot in RAG since only the top-k results actually make it into the LLM's prompt."),
                    ("medium", "What is \"answer relevance\" as distinct from \"faithfulness\" in RAG evaluation?",
                     "Faithfulness checks whether the answer's claims are supported by the retrieved context (is it making things up?). Answer relevance checks something orthogonal: whether the answer actually addresses what the user asked, regardless of whether it's faithful - an answer can be perfectly faithful to the retrieved context while still failing to actually answer the question asked, e.g. by answering a related-but-different question the context happened to cover."),
                    ("hard", "Why is a purely automated, LLM-as-judge evaluation pipeline not a complete substitute for human evaluation in RAG?",
                     "An LLM judge can inherit the same blind spots and biases as the models it's evaluating (rewarding fluent-sounding wrong answers, missing subtle factual errors it wouldn't catch in its own generation either), and its judgments are themselves probabilistic and not perfectly calibrated to real user satisfaction. Automated evaluation is valuable for fast, cheap, repeatable regression detection across many pipeline changes, but periodic human review remains necessary to catch failure modes the automated judge systematically misses and to validate that the automated metric is actually still tracking real quality."),
                ],
            },
        ],
    },
    {
        "topic": "LangChain",
        "short_label": "LangChain",
        "category": "AI/LLM",
        "subtopics": [
            {
                "name": "Core Concepts",
                "content": (
                    "LangChain is a framework for building applications powered by large language models, "
                    "providing standardized abstractions for the patterns that recur across nearly every "
                    "LLM application: formatting prompts, chaining multiple calls together, maintaining "
                    "conversation memory, integrating retrieval for RAG, and building agents that can decide "
                    "to call external tools. The motivation is that a raw LLM API call is a single, "
                    "stateless request-response - almost any real application needs to wrap that call with "
                    "surrounding orchestration logic (assembling context, parsing structured output, "
                    "remembering prior turns, deciding what to do next), and LangChain exists so developers "
                    "aren't rebuilding that same plumbing from scratch on every project.\n\n"
                    "The framework's modern core is LCEL (LangChain Expression Language), a declarative way "
                    "to compose components using the `|` (pipe) operator - `prompt | model | output_parser` "
                    "- similar in spirit to Unix pipes, where each component's output feeds directly into "
                    "the next. Every composable piece (prompts, models, retrievers, output parsers) "
                    "implements a common `Runnable` interface standardizing `invoke`, `batch`, `stream`, and "
                    "their async equivalents across otherwise very different component types - which is "
                    "exactly what makes piping arbitrary components together with `|` work uniformly, and "
                    "why LCEL chains automatically gain streaming, batching, and async support with no extra "
                    "code, unlike LangChain's older, more imperative chain classes. LangChain's broad "
                    "provider-agnostic interface also makes swapping the underlying LLM relatively "
                    "mechanical - though real prompt behavior still varies enough across providers that a "
                    "swap rarely means zero retuning."
                ),
                "questions": [
                    ("easy", "What is LangChain, at a high level?",
                     "LangChain is a framework for building applications powered by LLMs, providing abstractions for common patterns - prompt templates, chains (sequences of calls), memory (conversation state), retrieval integration (for RAG), and agents (LLMs that can decide to call tools) - so developers don't build this orchestration plumbing from scratch for every project."),
                    ("easy", "What is a \"chain\" in LangChain?",
                     "A chain is a sequence of calls - to an LLM, a tool, a data source, or another chain - composed to accomplish a task a single LLM call can't cleanly do, such as taking user input, formatting a prompt, calling the LLM, and parsing the output into structured form, all as one composed unit."),
                    ("medium", "What is LCEL (LangChain Expression Language), and what's its advantage over older chain classes?",
                     "LCEL is a declarative way to compose chains using the `|` (pipe) operator to connect components (prompt | model | output_parser), similar to Unix pipes. Compared to older imperative chain classes, LCEL components automatically support streaming, async execution, and batching without extra code."),
                    ("medium", "What is a Runnable in LangChain (the LCEL context)?",
                     "Runnable is the core interface every composable component implements (prompts, models, output parsers, retrievers) - standardizing invoke/batch/stream/ainvoke across otherwise different component types, which is exactly what makes piping them together with `|` work uniformly."),
                    ("hard", "How does LangChain's abstraction help with switching LLM providers, and what's a limitation?",
                     "LangChain provides a common interface across many providers, so swapping often just means changing which model class you instantiate, with the rest of your chain unchanged. The limitation: providers differ in real capabilities (context length, structured output support, refusal behavior) a thin common interface can't fully paper over - a prompt tuned for one model's quirks may need retuning for another even after the mechanical swap."),
                    ("easy", "What is the difference between a \"model\" and a \"chat model\" abstraction in LangChain?",
                     "A plain (completion-style) model takes a text string and returns a text string, matching older LLM APIs. A chat model takes a list of role-tagged messages (system/human/AI) and returns a message, matching the message-based structure that virtually all modern LLM APIs (OpenAI, Anthropic, Google, etc.) actually use - LangChain's ChatModel abstraction is the one almost universally used today."),
                    ("medium", "What does it mean that LangChain components are \"composable,\" and why does that matter for maintainability?",
                     "Composability means small, single-purpose components (a prompt template, a model call, an output parser, a retriever) can be connected together into larger pipelines without each one needing to know the internal details of the others - only the shared Runnable interface. This matters for maintainability because a change to one component (swapping a retriever, adjusting a prompt) doesn't ripple through the rest of the pipeline, the same benefit modular design gives any software system."),
                    ("hard", "What are the tradeoffs of using a framework like LangChain versus calling an LLM provider's SDK directly?",
                     "LangChain provides ready-made abstractions for common patterns (chains, memory, retrieval, agents) and provider-agnostic interfaces, saving significant development time for applications that need several of these patterns together. The tradeoffs: an added abstraction layer to learn, occasional friction when you need a provider-specific feature the abstraction doesn't cleanly expose, and a dependency on the framework's own release cadence and breaking changes. For a very simple, single-purpose LLM call, calling the provider's SDK directly is often simpler and has less indirection."),
                ],
            },
            {
                "name": "Prompts & Prompt Templates",
                "content": (
                    "A PromptTemplate defines a reusable prompt containing named placeholder variables, "
                    "validated against whatever variables are actually supplied at formatting time - "
                    "more robust than an ad hoc f-string, and one that integrates cleanly with the rest of "
                    "LangChain's composition system (LCEL piping, few-shot example selection, output "
                    "parsers that inject their own formatting instructions into the same template). "
                    "ChatPromptTemplate extends this to the message-based structure modern chat APIs "
                    "actually expect: instead of producing a single formatted string, it produces a "
                    "structured list of role-tagged messages (system, human, AI), letting you template an "
                    "entire multi-turn conversation shape - including a system prompt - rather than just one "
                    "flat block of text.\n\n"
                    "Few-shot prompting - including example input/output pairs in the prompt before the "
                    "actual query, to demonstrate the desired output pattern - often measurably improves "
                    "output quality and consistency over a bare zero-shot instruction; LangChain's "
                    "FewShotPromptTemplate and example selectors (which can dynamically pick the most "
                    "relevant examples for a given input, e.g. by embedding similarity) manage this "
                    "systematically rather than hardcoding a fixed example set into every prompt. Output "
                    "parsers are the natural counterpart to prompt templates: they convert an LLM's raw text "
                    "response into a specific, usable Python type (a Pydantic model, structured JSON), and "
                    "many parsers also generate the formatting instructions injected back into the prompt "
                    "itself (\"respond using exactly this JSON schema\") - prompt and parser really function "
                    "as two halves of one contract. Where a provider supports native structured output or "
                    "function-calling at the decoding level, that's generally more reliable than "
                    "prompt-based formatting instructions alone, since the model can still deviate from "
                    "purely textual formatting instructions in ways native constrained decoding prevents "
                    "outright - at the cost of being provider-specific rather than universally available."
                ),
                "questions": [
                    ("easy", "What is a PromptTemplate, and why use one instead of an f-string?",
                     "A PromptTemplate defines a reusable prompt with named placeholder variables, validated against the variables actually provided when formatting it. It also integrates with the rest of LangChain's composition system (LCEL piping, few-shot example selectors, output parsers) in ways a bare f-string wouldn't."),
                    ("medium", "What is a ChatPromptTemplate, and how does it differ from a plain PromptTemplate?",
                     "PromptTemplate produces a single formatted text string, suited to older completion-style models. ChatPromptTemplate produces a structured list of role-tagged messages (system, human, AI) suited to modern chat-based APIs, letting you template a full multi-turn conversation structure including a system prompt."),
                    ("medium", "What is few-shot prompting, and how does LangChain support it structurally?",
                     "Few-shot prompting includes example input/output pairs in the prompt to demonstrate desired behavior before the actual query, often improving output quality/consistency over zero-shot. LangChain's FewShotPromptTemplate (and example selectors, which can dynamically choose the most relevant examples, e.g. by similarity) manage and format examples systematically."),
                    ("hard", "What is an output parser, and why is it often paired directly with the prompt template?",
                     "An output parser converts the LLM's raw output into a specific Python type (a Pydantic model, JSON) the application can use programmatically. It's paired with the prompt because many parsers also generate formatting instructions injected into the prompt (\"respond in this exact JSON schema\") so the model is actually likely to produce parseable output - prompt and parser are two halves of the same contract."),
                    ("hard", "What are the tradeoffs of prompt-based formatting instructions vs. native structured-output/function-calling?",
                     "Prompt-based instructions work across any model regardless of native support, but the model can still deviate (extra prose, malformed JSON), requiring parsing retries. Native structured-output features constrain generation at the decoding level, producing much more reliable output, at the cost of being provider-specific and not universally available."),
                    ("easy", "What are the typical message roles in a ChatPromptTemplate, and what does each represent?",
                     "system sets model behavior/persona/instructions that apply for the whole conversation and isn't itself a turn in the dialogue. human represents a message from the user. AI represents a prior response from the model - included when templating multi-turn history so the model sees its own earlier turns as context. Some providers also support a distinct tool/function role for tool-call results being fed back to the model."),
                    ("medium", "What is a partial prompt template, and when is it useful?",
                     "A partial template pre-fills some of a PromptTemplate's variables ahead of time (e.g. always injecting today's date, or a fixed system instruction) while leaving others to be supplied later at actual invocation time. It's useful for splitting a template's variables into ones known early (config-time) versus ones only known per-request (user input), avoiding having to pass every value through every call site."),
                    ("hard", "How do prompt templates interact with token-limit constraints, and what strategies address running over budget?",
                     "A template's rendered length (base instructions plus injected variables like retrieved context, conversation history, or few-shot examples) all counts against the model's context window, and a template that works fine with short inputs can silently exceed the limit once fed a long document or long conversation history. Strategies include truncating or summarizing injected content before insertion, dynamically selecting fewer few-shot examples or retrieved chunks when the base input is already long, and using a tokenizer to check the fully-rendered prompt's length before sending it, rather than assuming static template size."),
                ],
            },
            {
                "name": "Chains & Composition",
                "content": (
                    "Many real tasks don't fit cleanly into one LLM call and benefit from being decomposed "
                    "into an ordered sequence of steps, where one step's output becomes the next step's "
                    "input - summarize a document, then generate quiz questions from that summary, for "
                    "instance. This is what a sequential chain (or its LCEL equivalent, piping components in "
                    "sequence) expresses directly. Not every task follows a fixed sequence, though: a router "
                    "chain first examines the input and dynamically decides which of several downstream "
                    "chains to invoke - classifying an incoming support question as \"billing\" versus "
                    "\"technical\" and routing to a specialized, purpose-tuned prompt for that category, "
                    "rather than forcing one generic chain to handle every input type equally well (which it "
                    "usually can't).\n\n"
                    "LCEL provides composition primitives beyond simple sequential piping: "
                    "`RunnableParallel` (also called `RunnableMap`) runs multiple Runnables concurrently on "
                    "the same input and merges their outputs into a single dictionary keyed by assigned "
                    "names - useful whenever a downstream step needs several independently-computed inputs "
                    "at once (running a retriever and a separate summarizer concurrently, rather than paying "
                    "their combined latency sequentially). Combining multiple retrievers or data sources "
                    "within one chain follows the same principles: run them in parallel and merge/deduplicate "
                    "results, or chain them so one retriever's output shapes a query to the next (fetch "
                    "relevant document IDs from a lightweight metadata index first, then full content for "
                    "just those from a heavier vector store). Production chains also need resilience: LCEL "
                    "Runnables support `.with_retry()` for automatic retries with configurable backoff on "
                    "failure, and `.with_fallbacks()` to specify an alternate Runnable to try if the primary "
                    "fails even after retries - falling back from a primary LLM provider to a secondary one "
                    "is a common real use, composing naturally with the same piping syntax as everything else."
                ),
                "questions": [
                    ("easy", "What is a SequentialChain (or its LCEL equivalent), and when would you use one?",
                     "A sequential chain runs multiple steps in order, where one step's output becomes the next step's input - e.g. summarize a document, then generate quiz questions from that summary. Used whenever a task naturally decomposes into ordered sub-steps better handled as distinct, focused LLM calls than one combined prompt."),
                    ("medium", "What's the difference between a \"simple\" chain and a \"router\" chain?",
                     "A simple chain always follows the same fixed sequence. A router chain examines the input first and dynamically decides which of several downstream chains to invoke - e.g. classifying a question as \"billing\" vs. \"technical support\" and routing to a specialized prompt for that category, rather than one generic chain for every input type."),
                    ("medium", "How do you combine multiple retrievers or data sources within a single chain?",
                     "Compose multiple retriever Runnables and merge results (e.g. running them in parallel via RunnableParallel and combining/deduplicating documents before the prompt), or chain them sequentially where one retriever's output informs a query to another (retrieve relevant IDs from a metadata store, then full content for just those from a vector store)."),
                    ("hard", "What is RunnableParallel/RunnableMap in LCEL used for?",
                     "It runs multiple Runnables concurrently on the same input and combines their outputs into a single dictionary keyed by assigned names - useful when a downstream step needs several independently-computed inputs at once, e.g. running a retriever and a summarizer in parallel rather than sequentially paying combined latency."),
                    ("hard", "How would you add retry and fallback logic to an LCEL chain?",
                     "LCEL Runnables support `.with_retry()` to automatically retry a step on failure with configurable backoff/max attempts, and `.with_fallbacks()` to specify alternate Runnables to try if the primary fails after retries - e.g. falling back from a primary LLM provider to a secondary one, composing naturally with the same piping syntax."),
                    ("easy", "What is RunnablePassthrough used for in an LCEL chain?",
                     "RunnablePassthrough forwards its input unchanged to the next step, most commonly used inside a RunnableParallel/dict step when you need the original input to survive alongside a transformed value - e.g. `{\"context\": retriever, \"question\": RunnablePassthrough()}` keeps the original question available to the prompt template alongside the retriever's output, rather than the question being lost once the retriever consumes it."),
                    ("medium", "What is the benefit of streaming support in an LCEL chain, and which use cases need it?",
                     "Streaming lets partial output (tokens as they're generated) reach the caller incrementally rather than waiting for the entire response to finish, which every Runnable in an LCEL chain supports automatically via `.stream()`. It matters most for user-facing chat interfaces, where showing tokens as they arrive gives dramatically better perceived responsiveness than a long silent wait followed by the full answer appearing at once."),
                    ("hard", "How would you design a chain that needs to branch based on an intermediate result, beyond simple routing?",
                     "Beyond a router chain (choosing between fixed alternative chains upfront), LCEL supports RunnableBranch for conditional logic based on a predicate evaluated against the current input/intermediate value, selecting among several candidate Runnables purely in code rather than requiring an extra LLM call just to decide the branch. For genuinely open-ended, LLM-decided branching (where the model itself determines what to do next based on evolving results), that's really the domain of an agent rather than a static chain - a static chain's branches are still ultimately fixed at chain-construction time, even if the condition is evaluated dynamically."),
                ],
            },
            {
                "name": "Agents & Tools",
                "content": (
                    "The distinction between a chain and an agent is really about where control flow lives. "
                    "A chain follows a fixed, predetermined sequence of steps regardless of what the input "
                    "actually turns out to need. An agent instead uses the LLM itself, at runtime, to decide "
                    "what to do next - which tool to call, with what arguments, or whether it already has "
                    "enough information to produce a final answer and stop. A \"tool\" in this context is "
                    "simply a function wrapped with a name, a natural-language description, and an input "
                    "schema, exposed to the agent as something it can choose to invoke - a calculator, a web "
                    "search, a database query. The agent's ability to use a tool correctly depends entirely "
                    "on that description being clear and accurate (since the LLM decides whether to call it "
                    "purely from reading the description) and the input schema being well-defined enough "
                    "that generated arguments can be reliably parsed and passed through.\n\n"
                    "The ReAct (Reason + Act) pattern underlies many agent implementations: the model "
                    "alternates between explicit reasoning (\"Thought: I need to look up X\") and taking an "
                    "action (invoking a tool), observing the result before deciding its next step, looping "
                    "until it judges it has enough information to give a final answer. Giving an LLM agent "
                    "access to tools with real side effects introduces real risk, since tool selection and "
                    "argument generation are inherently probabilistic: the model can call the wrong tool, "
                    "generate malformed arguments, or be manipulated by adversarial content it encounters "
                    "mid-task (a prompt-injection risk when a tool result, like a web page, contains text "
                    "crafted to redirect the agent's behavior). Sensible mitigations include human-in-the-loop "
                    "confirmation before high-consequence actions, scoping each tool's permissions as "
                    "narrowly as possible, and validating tool inputs rather than trusting generated "
                    "arguments blindly. When an agent gets stuck in a loop repeatedly calling the same tool "
                    "without making progress, inspecting its intermediate reasoning trace (via verbose "
                    "logging or a tracing tool like LangSmith) usually reveals the real cause - often that "
                    "the tool's output isn't answering what the model actually needed, or the observation "
                    "format is confusing it about whether it has enough information to stop."
                ),
                "questions": [
                    ("easy", "What is an \"agent\" in LangChain, as distinct from a plain chain?",
                     "A plain chain follows a fixed, predetermined sequence regardless of input. An agent uses an LLM to decide at runtime what actions to take next (which tool to call, with what arguments, or when to stop) - control flow is determined dynamically by the model's reasoning, not hardcoded in advance."),
                    ("medium", "What is a \"tool\" in LangChain, and what does an agent need to use one correctly?",
                     "A tool is a function (wrapped with a name, description, and input schema) an agent can choose to invoke - a calculator, a web search, a database query. It needs a clear, accurate description (the LLM decides whether to call it based on that) and a well-defined input schema so generated arguments can be reliably parsed and passed through."),
                    ("medium", "What is the ReAct pattern, and how does it relate to LangChain agents?",
                     "ReAct (Reason + Act) is a prompting pattern where the model alternates between explicit reasoning (\"Thought: I need to look up X\") and actions (calling a tool), observing each result before deciding the next step, looping until it has enough information for a final answer. Many LangChain agent implementations are built directly on this reason-act-observe loop."),
                    ("hard", "What are the main risks of giving an LLM agent access to tools with real side effects?",
                     "Tool-selection and argument-generation are probabilistic and can be wrong - calling the wrong tool, malformed arguments, being manipulated by adversarial content encountered during a search (prompt injection), or misjudging that an action is appropriate. Mitigations: human-in-the-loop confirmation before high-consequence actions, scoping tool permissions narrowly, and validating tool inputs rather than trusting the model blindly."),
                    ("hard", "How would you debug an agent stuck in a loop repeatedly calling the same tool without progress?",
                     "Inspect the agent's intermediate reasoning trace (verbose/tracing output, or LangSmith) to see what the model is \"thinking\" and why it keeps re-invoking the tool - often the tool's output isn't answering what the model needed, the observation format is confusing it, or it's not recognizing sufficient information to stop. Fixes: clarify the tool's description/output format, add a max-iteration safety limit, or restructure the prompt to signal when to conclude."),
                    ("easy", "Why does a tool's description matter as much as its actual implementation?",
                     "The agent never reads a tool's source code - it decides whether and how to call a tool purely by reading its name, description, and parameter schema at prompt-construction time. A perfectly correct tool with a vague or misleading description will be called incorrectly or not at all, since from the model's perspective the description IS the tool's entire interface; a clear, accurate description is as much a functional requirement as correct implementation."),
                    ("medium", "What is a max-iteration or max-steps limit on an agent, and why is it necessary?",
                     "It's a hard cap on how many reasoning/tool-call cycles an agent is allowed to run before being forced to stop and return whatever it has, regardless of whether it judges itself done. It's necessary because an agent can otherwise loop indefinitely (never converging on a stopping condition) or run unboundedly long chains of tool calls, which without a cap could run forever, cost unbounded tokens, and in the case of tools with side effects, take an unbounded number of real-world actions."),
                    ("hard", "What is the difference between a single-tool agent and a multi-tool agent in terms of design complexity?",
                     "A single-tool agent only needs to decide *when* to call its one tool and how to format the arguments - a comparatively simple decision. A multi-tool agent additionally needs to correctly select *which* tool among several is appropriate for a given sub-task, which becomes markedly harder as the tool set grows and tools have overlapping or ambiguous applicability - clear, mutually distinguishable tool descriptions become increasingly critical, and some architectures introduce a dedicated routing/planning step specifically to make that tool-selection decision more reliable than leaving it to a single undifferentiated prompt."),
                ],
            },
            {
                "name": "Memory",
                "content": (
                    "LLM API calls are stateless by default: each call has no inherent awareness of any "
                    "prior interaction unless the full relevant conversation history is explicitly included "
                    "in that call's prompt. \"Memory\" in LangChain refers to the components that manage this "
                    "history on the application's behalf - storing past turns, retrieving them, and "
                    "formatting them back into each new prompt - so a conversational chain can maintain "
                    "context across a multi-turn interaction without the surrounding application code "
                    "manually managing a raw message list at every call site. The simplest approach, buffer "
                    "memory, stores the raw conversation history verbatim and includes the most recent N "
                    "turns in each new prompt - simple and faithful to what was actually said, but it grows "
                    "unbounded as a conversation continues and will eventually exceed the model's context "
                    "window if left unchecked.\n\n"
                    "Summary memory addresses that growth problem by periodically condensing older parts of "
                    "the conversation into a running summary (itself generated via an LLM call), keeping "
                    "only the most recent turns verbatim while replacing everything older with a compact "
                    "summary - trading some fidelity to the exact original wording for a bounded, scalable "
                    "prompt size regardless of how long the conversation runs. Entity memory takes a "
                    "different angle: rather than tracking the whole transcript, it extracts and persists "
                    "specific facts about named entities mentioned in conversation (\"the user's name is "
                    "Alex, works at Acme\") into a structured store, which is valuable when specific facts "
                    "need to remain reliably available even long after the message that originally mentioned "
                    "them has aged out of any buffer window. For memory that needs to persist across "
                    "genuinely separate user sessions (not just within one continuous conversation), the "
                    "right approach is backing it with real persistent storage - a database or key-value "
                    "store keyed by user or session ID, loaded at the start of each interaction and saved "
                    "after each turn - with real design questions around how much history to retain "
                    "long-term, data-retention/privacy policy, and whether memory should persist indefinitely "
                    "or reset after a period of inactivity. At larger scale, even memory itself can become a "
                    "retrieval problem: rather than including full history in every prompt (which doesn't "
                    "scale and dilutes attention with irrelevant old turns), embedding past turns and "
                    "retrieving only the most relevant ones - the same core idea as RAG - scales far better "
                    "to genuinely long-running conversations."
                ),
                "questions": [
                    ("easy", "What problem does \"memory\" solve in a LangChain conversational application?",
                     "LLM API calls are stateless by default - each call has no awareness of prior turns unless the conversation history is explicitly included in the prompt. Memory components manage that history (storing, retrieving, formatting past turns) so a conversational chain maintains context across interactions without manually managing a raw message list."),
                    ("medium", "What's the difference between buffer memory and summary memory?",
                     "Buffer memory stores the raw conversation history verbatim, including the most recent N turns in each new prompt - simple, but grows unbounded and can eventually exceed the context window. Summary memory periodically condenses older parts into a running summary (via an LLM call), keeping recent turns verbatim but replacing older history with a compact summary - trading fidelity for bounded, scalable size."),
                    ("medium", "What is entity memory, and when is it more useful than a simple message buffer?",
                     "Entity memory extracts and tracks specific facts about named entities mentioned in conversation (e.g. \"the user's name is Alex, works at Acme\") into a structured store, rather than keeping the entire raw transcript. It's useful when specific facts need to persist reliably even after the original mentioning message ages out of a buffer window."),
                    ("hard", "How would you implement memory persisting across separate user sessions, and what are the design considerations?",
                     "Back it with persistent storage (a database/key-value store) keyed by user or session ID, loaded at the start of each interaction and saved after each turn, instead of keeping memory in-process. Considerations: how much history to retain long-term (raw vs. summarized) to avoid unbounded growth, privacy/data-retention policy, and whether memory should persist indefinitely or reset after inactivity."),
                    ("hard", "What's the tradeoff of full conversation memory in every prompt vs. retrieving only relevant past context?",
                     "Full memory in every prompt is simple but doesn't scale - token cost grows with conversation length, and irrelevant old turns dilute attention on what's relevant now. Treating memory as a retrieval problem (embedding past turns and retrieving only the most relevant, similar to RAG) scales better to long-running conversations, at the cost of added complexity and the same retrieval-quality risks any RAG-style system faces."),
                    ("easy", "Why can't an LLM \"remember\" a previous conversation on its own, without an application managing memory?",
                     "Each API call to an LLM provider is an independent, stateless request - the model has no persistent internal state between calls, and by default has no access to anything that isn't explicitly included in the current request's input. Any appearance of \"remembering\" earlier turns comes entirely from the calling application re-sending the relevant prior conversation as part of each new prompt, not from any memory the model itself retains."),
                    ("medium", "What is a sliding window approach to conversation memory, and what's its main drawback?",
                     "A sliding window keeps only the most recent N messages (or tokens) verbatim, dropping anything older outright rather than summarizing it - simpler than summary memory since it needs no extra LLM call. Its main drawback is that anything genuinely important said earlier in the conversation is permanently lost the moment it falls outside the window, with no compressed trace of it remaining at all, unlike summary memory which at least retains a condensed version."),
                    ("hard", "How would you decide between summary memory and retrieval-based memory for a long-running assistant application?",
                     "Summary memory is simpler to implement and keeps a single coherent narrative of the conversation, but progressively loses detail as older content gets compressed and re-compressed, and a summary generated early on can't recover a detail it summarized away too aggressively. Retrieval-based memory (embedding and retrieving relevant past turns on demand, like RAG) preserves the original detail indefinitely and can surface it precisely when relevant much later, at the cost of retrieval-quality risk (the same failure modes as any RAG system) and added infrastructure. Summary memory tends to suit shorter, single-session-focused assistants; retrieval-based memory suits assistants expected to recall specific facts accurately across very long or many separate sessions."),
                ],
            },
            {
                "name": "Retrieval & Integration (RAG in LangChain)",
                "content": (
                    "LangChain provides standardized building blocks for the same RAG pipeline concepts "
                    "that apply generally, wired together through its Runnable/LCEL composition system. A "
                    "Document Loader reads content from a specific source format (PDF, web page, CSV, "
                    "database) and converts it into LangChain's standard Document object - text content plus "
                    "metadata - giving a consistent interface regardless of the original source format, and "
                    "forming the first step in the pipeline before any splitting or embedding happens. A "
                    "TextSplitter then divides that Document's text into chunks suitable for embedding; "
                    "LangChain's RecursiveCharacterTextSplitter is the commonly-reached-for default over a "
                    "naive fixed-position splitter, since it tries a prioritized list of separators "
                    "(paragraph breaks, then sentence breaks, then word breaks) and only falls back to a "
                    "harder cut if a chunk still exceeds the target size, producing more semantically "
                    "coherent chunks than blindly cutting at a fixed character count.\n\n"
                    "A Retriever is LangChain's standard interface for anything that takes a query string and "
                    "returns relevant Documents - VectorStoreRetriever is the most common concrete "
                    "implementation, wrapping a vector store's similarity search behind this standard "
                    "interface, but because the interface is standard, it's straightforward to swap in a "
                    "non-vector-store retriever (a keyword-based one, a hybrid one, or a call to an external "
                    "API) without changing any of the surrounding chain logic that just expects \"something "
                    "that returns Documents for a query.\" A minimal RAG chain expressed in LCEL looks "
                    "roughly like `{\"context\": retriever, \"question\": RunnablePassthrough()} | "
                    "prompt_template | model | output_parser` - the retriever fetches relevant documents for "
                    "the incoming question, RunnablePassthrough forwards the original question unchanged, "
                    "both combine into a dictionary fed to the prompt template, the formatted prompt goes to "
                    "the model, and the output parser extracts the final answer. The broader value of "
                    "LangChain's integration ecosystem here is that swapping a vector store or embedding "
                    "provider is usually a small, localized change to one component rather than a rewrite of "
                    "the surrounding retrieval, prompting, and parsing logic, which stays decoupled from the "
                    "specific integration in use - the tradeoff being an additional abstraction layer to "
                    "learn, and occasional cases where a specific integration's unique features aren't fully "
                    "exposed through the generic interface."
                ),
                "questions": [
                    ("easy", "What is a Document Loader, and what role does it play in a RAG pipeline?",
                     "A Document Loader reads content from a specific source format (PDF, web page, CSV, database) and converts it into LangChain's standard Document object (text plus metadata), providing a consistent interface regardless of source format - the first step before splitting/chunking and embedding."),
                    ("medium", "What is a TextSplitter, and what's the difference between character-based and recursive character splitting?",
                     "A TextSplitter divides Document text into chunks suitable for embedding. A basic character splitter cuts at a fixed character count regardless of content. A RecursiveCharacterTextSplitter tries a prioritized list of separators (paragraphs, then sentences, then words), falling back to a harder cut only if a chunk is still too large - producing more semantically coherent chunks than a naive fixed-position cut."),
                    ("medium", "What is a Retriever interface, and how does it relate to a vector store?",
                     "A Retriever is a Runnable taking a query string and returning relevant Documents - a VectorStoreRetriever is the most common implementation, wrapping a vector store's similarity search behind this standard interface. Because it's standard, you can swap in non-vector-store retrievers (keyword, hybrid, an external API) without changing surrounding chain logic."),
                    ("hard", "How would you build a RAG chain in LangChain using LCEL, at a conceptual level?",
                     "Roughly: `chain = {\"context\": retriever, \"question\": RunnablePassthrough()} | prompt_template | model | output_parser` - the retriever fetches relevant documents for the incoming question, RunnablePassthrough forwards the question unchanged, both combine into a dict fed to the prompt template, the formatted prompt goes to the model, and the output parser extracts the final answer."),
                    ("hard", "What's the benefit of LangChain's integration ecosystem versus writing RAG plumbing from scratch?",
                     "Standard interfaces mean swapping a vector store or embedding provider is usually a small, localized change rather than a rewrite, since surrounding chain logic (retrieval, prompting, parsing) is decoupled from the specific integration. The tradeoff is an additional abstraction layer to learn and occasional lowest-common-denominator limitations where a specific integration's unique features aren't fully exposed."),
                    ("easy", "What is the Document object in LangChain, and what two things does it always carry?",
                     "A Document is LangChain's standard unit of content moving through a RAG pipeline, always carrying page_content (the actual text) and metadata (a dictionary of arbitrary source information - filename, page number, URL, access permissions, etc.). Keeping content and metadata bundled together means metadata survives all the way through splitting, embedding, and retrieval, available for filtering or citation at the point an answer is generated."),
                    ("medium", "What is the difference between a Retriever and a plain VectorStore's similarity_search method?",
                     "A VectorStore's similarity_search method is a direct, store-specific API call for finding similar documents. A Retriever wraps that (or any other retrieval mechanism) behind LangChain's standard Runnable interface, so it can be composed with `|` alongside prompts, models, and parsers in an LCEL chain exactly like any other component - the Retriever abstraction exists specifically so retrieval logic isn't tied to one vector store's particular API inside the rest of your chain."),
                    ("hard", "How would you incorporate metadata filtering into a LangChain RAG chain, at a conceptual level?",
                     "Most VectorStoreRetriever implementations accept search kwargs (like a `filter` parameter) passed through to the underlying vector store's native metadata filtering capability, so you can construct a retriever scoped to only search documents matching specific metadata conditions (e.g. a specific user's authorized documents) without changing anything else in the chain. For per-request dynamic filtering (e.g. the current authenticated user varies per call), the retriever is typically constructed or parameterized fresh per request rather than reused as one static, pre-built object, since the filter criteria themselves are request-specific."),
                ],
            },
        ],
    },
]


def build_result(topic_data: dict) -> GenerateResult:
    questions = [
        Question(category=subtopic["name"], difficulty=Difficulty(difficulty), question=q, answer=a)
        for subtopic in topic_data["subtopics"]
        for (difficulty, q, a) in subtopic["questions"]
    ]
    subtopic_content = [
        SubtopicContent(subtopic=subtopic["name"], content=subtopic["content"])
        for subtopic in topic_data["subtopics"]
    ]
    n = len(questions)
    return GenerateResult(
        topic=topic_data["topic"],
        questions=questions,
        subtopic_content=subtopic_content,
        eval=EvalReport(
            average_relevance=5.0,
            relevance_scores=[5.0] * n,
            max_pairwise_similarity=0.0,
            duplication_flagged=False,
        ),
        metrics=RunMetrics(total_latency_ms=0.0, step_latencies_ms={}, total_input_tokens=0, total_output_tokens=0),
        from_cache=False,
        curated=True,
    )


def upsert_topic_label(session: Session, topic_key: str, topic: str, short_label: str, category: str) -> None:
    existing = session.exec(select(TopicLabel).where(TopicLabel.topic_key == topic_key)).first()
    if existing:
        existing.topic = topic
        existing.short_label = short_label
        existing.category = category
        session.add(existing)
    else:
        session.add(TopicLabel(topic_key=topic_key, topic=topic, short_label=short_label, category=category))
    session.commit()


def upsert_search_history(session: Session, user_id: int, topic_key: str) -> None:
    existing = session.exec(
        select(SearchHistory).where(SearchHistory.user_id == user_id, SearchHistory.topic_key == topic_key)
    ).first()
    if existing:
        existing.last_searched_at = datetime.utcnow()
        session.add(existing)
    else:
        session.add(SearchHistory(user_id=user_id, topic_key=topic_key, last_searched_at=datetime.utcnow()))
    session.commit()


def main() -> None:
    init_db()

    with Session(engine) as session:
        owner = session.exec(select(User).where(User.email == settings.owner_email)).first()
        if owner is None:
            raise SystemExit(
                f"No owner user found for {settings.owner_email!r} - start the app once first "
                "so it bootstraps the owner account, then re-run this script."
            )

        for topic_data in TOPICS:
            key = normalize_topic(topic_data["topic"])
            result = build_result(topic_data)

            # Same code path as a real cache write - no LLM call anywhere in this script.
            save_to_cache(topic_data["topic"], result, session)
            upsert_topic_label(session, key, topic_data["topic"], topic_data["short_label"], topic_data["category"])
            upsert_search_history(session, owner.id, key)

            question_count = sum(len(s["questions"]) for s in topic_data["subtopics"])
            print(
                f"Seeded {topic_data['topic']!r}: {len(topic_data['subtopics'])} subtopics, "
                f"{question_count} questions, category={topic_data['category']!r}"
            )

    print("\nDone. These topics will now show as instant, zero-cost cache hits, and appear in the owner's past searches.")


if __name__ == "__main__":
    main()
