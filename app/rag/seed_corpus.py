"""A small, hand-written reference corpus spanning common technical
interview topics. Grounds question generation - it's deliberately short
(breadth over depth) since its job is to nudge Claude toward accurate,
idiomatic terminology, not to be an authoritative source. Retrieval is by
embedding similarity, so a topic like "SQL" or "postgres joins" both surface
the same relevant chunks without any keyword matching.
"""

SEED_CORPUS: list[dict[str, str]] = [
    {"id": "sql-joins", "text": "SQL joins combine rows from two or more tables based on a related column. INNER JOIN returns only matching rows; LEFT JOIN keeps all rows from the left table with NULLs for non-matches; FULL OUTER JOIN keeps unmatched rows from both sides."},
    {"id": "sql-indexing", "text": "A database index is usually a B-tree structure that speeds up row lookups at the cost of extra storage and slower writes, since every insert, update, or delete must also update the index."},
    {"id": "sql-normalization", "text": "Normalization organizes relational tables to reduce redundancy: 1NF eliminates repeating groups, 2NF removes partial dependencies on a composite key, and 3NF removes transitive dependencies on non-key columns."},
    {"id": "sql-transactions", "text": "ACID describes transaction guarantees: Atomicity (all-or-nothing), Consistency (valid state transitions only), Isolation (concurrent transactions don't see each other's partial effects), and Durability (committed data survives a crash)."},
    {"id": "sql-window-functions", "text": "Window functions like ROW_NUMBER(), RANK(), and SUM() OVER(PARTITION BY ...) compute a value across a set of related rows without collapsing them into a single output row, unlike GROUP BY."},
    {"id": "python-decorators", "text": "A Python decorator is a function that wraps another function to extend its behavior without modifying its source, using the @decorator syntax as sugar for func = decorator(func)."},
    {"id": "python-gil", "text": "CPython's Global Interpreter Lock (GIL) allows only one thread to execute Python bytecode at a time, which limits CPU-bound multithreading but does not affect multiprocessing or I/O-bound async code."},
    {"id": "python-generators", "text": "A generator function uses yield to produce a lazy sequence of values one at a time, pausing its state between calls, which keeps memory usage low for large or infinite sequences."},
    {"id": "dsa-big-o", "text": "Big-O notation describes how an algorithm's runtime or memory use scales with input size in the worst case, focusing on the dominant term as the input grows large (e.g. O(n log n) for a good sort)."},
    {"id": "dsa-hash-tables", "text": "A hash table maps keys to values using a hash function to compute a bucket index, giving average O(1) lookup, insert, and delete; collisions are handled via chaining or open addressing."},
    {"id": "dsa-trees", "text": "A binary search tree keeps left children smaller and right children larger than their parent, giving O(log n) search on average, but can degrade to O(n) if unbalanced - self-balancing variants like AVL or red-black trees prevent that."},
    {"id": "dsa-graphs", "text": "Graph traversal algorithms include BFS (level by level, using a queue, finds shortest path in unweighted graphs) and DFS (goes deep first, using a stack or recursion, useful for cycle detection and topological sort)."},
    {"id": "sysdesign-load-balancing", "text": "A load balancer distributes incoming requests across multiple backend servers, commonly using round-robin, least-connections, or consistent hashing, to improve availability and horizontal scalability."},
    {"id": "sysdesign-caching", "text": "Caching stores frequently accessed data in a fast layer (in-memory, CDN, or local) to reduce load on the primary data store; cache invalidation and staleness are the classic hard problems."},
    {"id": "sysdesign-sharding", "text": "Sharding splits a dataset across multiple database instances by a partition key, allowing horizontal scaling of writes, at the cost of harder cross-shard queries and joins."},
    {"id": "sysdesign-cap-theorem", "text": "The CAP theorem states a distributed system can only guarantee two of Consistency, Availability, and Partition tolerance at once during a network partition - since partitions are unavoidable, real systems choose between consistency and availability."},
    {"id": "networking-tcp-udp", "text": "TCP is connection-oriented and guarantees ordered, reliable delivery via acknowledgments and retransmission; UDP is connectionless and unreliable but has lower overhead, making it suited to real-time use cases like video or gaming."},
    {"id": "networking-http", "text": "HTTP is a stateless request-response protocol; HTTP/1.1 added persistent connections and pipelining, while HTTP/2 introduced multiplexed streams over a single connection to avoid head-of-line blocking at the application layer."},
    {"id": "networking-dns", "text": "DNS resolves human-readable domain names to IP addresses through a hierarchy of resolvers, root servers, TLD servers, and authoritative name servers, with results cached at each layer according to a TTL."},
    {"id": "oop-solid", "text": "SOLID summarizes five OOP design principles: Single responsibility, Open/closed, Liskov substitution, Interface segregation, and Dependency inversion - aimed at code that's easier to extend without modifying existing, tested logic."},
    {"id": "oop-polymorphism", "text": "Polymorphism lets code call the same method on different types and get type-appropriate behavior, typically via inheritance and method overriding, or via interfaces/duck typing in dynamically typed languages."},
    {"id": "distributed-consensus", "text": "Consensus algorithms like Paxos and Raft let a cluster of nodes agree on a single value or sequence of operations even if some nodes fail, forming the basis of distributed logs and leader election."},
    {"id": "distributed-idempotency", "text": "An idempotent operation produces the same result no matter how many times it's applied, which is essential for safely retrying requests over an unreliable network without risking duplicate side effects."},
    {"id": "security-authn-authz", "text": "Authentication verifies who a user is (e.g. password, token, biometric); authorization determines what an authenticated user is allowed to do. Conflating the two is a common source of access-control bugs."},
    {"id": "security-hashing", "text": "Passwords should be stored as salted hashes using a slow, purpose-built algorithm like bcrypt or argon2, never plain text or a fast general-purpose hash like MD5 or SHA-256, which are easy to brute-force at scale."},
    {"id": "testing-pyramid", "text": "The testing pyramid favors many fast, cheap unit tests, fewer integration tests, and few slow, brittle end-to-end tests - inverting that ratio tends to produce a slow, flaky suite that people stop trusting."},
    {"id": "git-branching", "text": "A pull request proposes merging one branch into another, typically after code review and passing CI checks; rebasing rewrites commit history to a linear sequence, while merging preserves the branch's actual history via a merge commit."},
]
