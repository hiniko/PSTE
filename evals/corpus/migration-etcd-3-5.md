### Server upgrade checklists

#### Upgrade requirements

To upgrade an existing etcd deployment to 3.5, the running cluster must be 3.4 or greater. If it's before 3.4, please [upgrade to 3.4](../upgrade_3_3/) before upgrading to 3.5.

Also, to ensure a smooth rolling upgrade, the running cluster must be healthy. Check the health of the cluster by using the `etcdctl endpoint health` command before proceeding.

#### Preparation

Before upgrading etcd, always test the services relying on etcd in a staging environment before deploying the upgrade to the production environment.

Before beginning, [download the snapshot backup](../../op-guide/maintenance/#snapshot-backup). Should something go wrong with the upgrade, it is possible to use this backup to [downgrade](#downgrade) back to existing etcd version. Please note that the `snapshot` command only backs up the v3 data. For v2 data, see [backing up v2 datastore](/docs/v2.3/admin_guide#backing-up-the-datastore).

#### Mixed versions

While upgrading, an etcd cluster supports mixed versions of etcd members, and operates with the protocol of the lowest common version. The cluster is only considered upgraded once all of its members are upgraded to version 3.5. Internally, etcd members negotiate with each other to determine the overall cluster version, which controls the reported version and the supported features.

#### Limitations

Note: If the cluster only has v3 data and no v2 data, it is not subject to this limitation.

If the cluster is serving a v2 data set larger than 50MB, each newly upgraded member may take up to two minutes to catch up with the existing cluster. Check the size of a recent snapshot to estimate the total data size. In other words, it is safest to wait for 2 minutes between upgrading each member.

For a much larger total data size, 100MB or more , this one-time process might take even more time. Administrators of very large etcd clusters of this magnitude can feel free to contact the [etcd team][etcd-contact] before upgrading, and we'll be happy to provide advice on the procedure.

#### Downgrade

If all members have been upgraded to v3.5, the cluster will be upgraded to v3.5, and downgrade from this completed state is **not possible**. If any single member is still v3.4, however, the cluster and its operations remains "v3.4", and it is possible from this mixed cluster state to return to using a v3.4 etcd binary on all members.

Please [download the snapshot backup](../../op-guide/maintenance/#snapshot-backup) to make downgrading the cluster possible even after it has been completely upgraded.
