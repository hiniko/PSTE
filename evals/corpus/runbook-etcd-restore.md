## Restoring an etcd cluster

If any API servers are running in your cluster, you should not attempt to
restore instances of etcd. Instead, follow these steps to restore etcd:

- stop *all* API server instances
- restore state in all etcd instances
- restart all API server instances

The Kubernetes project also recommends restarting Kubernetes components (`kube-scheduler`,
`kube-controller-manager`, `kubelet`) to ensure that they don't rely on some
stale data. In practice the restore takes a bit of time.  During the
restoration, critical components will lose leader lock and restart themselves.

etcd supports restoring from snapshots that are taken from an etcd process of
the [major.minor](https://semver.org/) version. Restoring a version from a
different patch version of etcd is also supported. A restore operation is
employed to recover the data of a failed cluster.

Before starting the restore operation, a snapshot file must be present. It can
either be a snapshot file from a previous backup operation, or from a remaining
[data directory](https://etcd.io/docs/current/op-guide/configuration/#--data-dir).

   When restoring the cluster using [`etcdutl`](https://github.com/etcd-io/etcd/blob/main/etcdutl/README.md),
   use the `--data-dir` option to specify to which folder the cluster should be restored:

   ```shell
   etcdutl --data-dir <data-dir-location> snapshot restore snapshot.db
   ```
   where `<data-dir-location>` is a directory that will be created during the restore process.


   The usage of `etcdctl` for restoring has been **deprecated** since etcd v3.5.x and is slated for removal from etcd v3.6.
   It is recommended to utilize [`etcdutl`](https://github.com/etcd-io/etcd/blob/main/etcdutl/README.md) instead.

   The below example depicts the usage of the `etcdctl` tool for the restore operation:

   ```shell
   export ETCDCTL_API=3
   etcdctl --data-dir <data-dir-location> snapshot restore snapshot.db
   ```

   If `<data-dir-location>` is the same folder as before, delete it and stop the etcd process before restoring the cluster. 
   Otherwise, change etcd configuration and restart the etcd process after restoration to have it use the new data directory:
   first change  `/etc/kubernetes/manifests/etcd.yaml`'s `volumes.hostPath.path` for `name: etcd-data`  to `<data-dir-location>`,
   then execute `kubectl -n kube-system delete pod <name-of-etcd-pod>` or `systemctl restart kubelet.service` (or both).


For more information and examples on restoring a cluster from a snapshot file, see
[etcd disaster recovery documentation](https://etcd.io/docs/current/op-guide/recovery/#restoring-a-cluster).

If the access URLs of the restored cluster are changed from the previous
cluster, the Kubernetes API server must be reconfigured accordingly. In this
case, restart Kubernetes API servers with the flag
`--etcd-servers=$NEW_ETCD_CLUSTER` instead of the flag
`--etcd-servers=$OLD_ETCD_CLUSTER`. Replace `$NEW_ETCD_CLUSTER` and
`$OLD_ETCD_CLUSTER` with the respective IP addresses. If a load balancer is
used in front of an etcd cluster, you might need to update the load balancer
instead.

If the majority of etcd members have permanently failed, the etcd cluster is
considered failed. In this scenario, Kubernetes cannot make any changes to its
current state. Although the scheduled pods might continue to run, no new pods
can be scheduled. In such cases, recover the etcd cluster and potentially
reconfigure Kubernetes API servers to fix the issue.


## Upgrading etcd clusters

Before you start an upgrade, back up your etcd cluster first.

For details on etcd upgrade, refer to the [etcd upgrades](https://etcd.io/docs/latest/upgrades/) documentation.

## Maintaining etcd clusters

For more details on etcd maintenance, please refer to the [etcd maintenance](https://etcd.io/docs/latest/op-guide/maintenance/) documentation.
