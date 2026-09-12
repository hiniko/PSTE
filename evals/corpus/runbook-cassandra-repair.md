== Incremental and Full Repairs

There are 2 types of repairs: full repairs, and incremental repairs.
Full repairs operate over all of the data in the token range being
repaired. Incremental repairs only repair data that's been written since
the previous incremental repair.

Incremental repairs are the default repair type, and if run regularly,
can significantly reduce the time and io cost of performing a repair.
However, it's important to understand that once an incremental repair
marks data as repaired, it won't try to repair it again. This is fine
for syncing up missed writes, but it doesn't protect against things like
disk corruption, data loss by operator error, or bugs in Cassandra. For
this reason, full repairs should still be run occasionally.

== Automated Repair Scheduling

Since repair can result in a lot of disk and network io, it has
traditionally not been run automatically by Cassandra.

In the latest version of Cassandra, a new feature called
xref:managing/operating/auto_repair.adoc[auto repair] was introduced to
allow Cassandra to submit and manage repairs automatically on a schedule.

The introduction of this feature does not interfere with existing repair
functionality enabled via nodetool.

== Submitting Repairs Using Nodetool

Repairs can also be run by the operator via nodetool.

Incremental repair is the default and is run with the following command:

[source,none]
----
nodetool repair
----

A full repair can be run with the following command:

[source,none]
----
nodetool repair --full
----

Additionally, repair can be run on a single keyspace:

[source,none]
----
nodetool repair [options] <keyspace_name>
----

Or even on specific tables:

[source,none]
----
nodetool repair [options] <keyspace_name> <table1> <table2>
----


The repair command repairs token ranges only on the node being repaired; it does not repair the whole cluster.
By default, repair operates on all token ranges replicated by the node on which repair is run, causing duplicate work when running it on every node. Avoid duplicate work by using the `-pr` flag to repair only the "primary" ranges on a node. 
Do a full cluster repair by running the `nodetool repair -pr` command on each node in each datacenter in the cluster, until all of the nodes and datacenters are repaired. 

The specific frequency of repair that's right for your cluster, of
course, depends on several factors. However, if you're just starting out
and looking for somewhere to start, running an incremental repair every
1-3 days, and a full repair every 1-3 weeks is probably reasonable. If
you don't want to run incremental repairs, a full repair every 5 days is
a good place to start.

At a minimum, repair should be run often enough that the gc grace period
never expires on unrepaired data. Otherwise, deleted data could
reappear. With a default gc grace period of 10 days, repairing every
node in your cluster at least once every 7 days will prevent this, while
providing enough slack to allow for delays.

== Other Options

`-pr, --partitioner-range`::
  Restricts repair to the 'primary' token ranges of the node being
  repaired. A primary range is just a token range for which a node is
  the first replica in the ring.
`-prv, --preview`::
  Estimates the amount of streaming that would occur for the given
  repair command. This builds the merkle trees, and prints the expected
  streaming activity, but does not actually do any streaming. By
  default, incremental repairs are estimated, add the `--full` flag to
  estimate a full repair.
`-vd, --validate`::
  Verifies that the repaired data is the same across all nodes. Similar
  to `--preview`, this builds and compares merkle trees of repaired
  data, but doesn't do any streaming. This is useful for
  troubleshooting. If this shows that the repaired data is out of sync,
  a full repair should be run.

`nodetool repair docs <nodetool_repair>`
