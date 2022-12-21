import json
from weakref import ref


DEFAULT_NAMESPACE = "default"
FLEET_DEFAULT_NAMESPACE = "fleet-default"


def merge_dict(src, dest):
    for k, v in src.items():
        if isinstance(dest.get(k), dict) and isinstance(v, dict):
            merge_dict(v, dest[k])
        else:
            dest[k] = v
    return dest


class BaseManager:
    def __init__(self, api):
        self._api = ref(api)

    @property
    def api(self):
        if self._api() is None:
            raise ReferenceError("API object no longer exists")
        return self._api()

    def _delegate(self, meth, path, *, raw=False, **kwargs):
        func = getattr(self.api, meth)
        resp = func(path, **kwargs)

        if raw:
            return resp
        try:
            return resp.status_code, resp.json()
        except json.decoder.JSONDecodeError as e:
            return resp.status_code, dict(error=e, response=resp)

    def _get(self, path, *, raw=False, **kwargs):
        return self._delegate("_get", path, raw=raw, **kwargs)

    def _create(self, path, *, raw=False, **kwargs):
        return self._delegate("_post", path, raw=raw, **kwargs)

    def _update(self, path, data, *, raw=False, as_json=True, **kwargs):
        if as_json:
            kwargs.update(json=data)
        else:
            kwargs.update(data=data)

        return self._delegate("_put", path, raw=raw, **kwargs)

    def _delete(self, path, *, raw=False, **kwargs):
        return self._delegate("_delete", path, raw=raw, **kwargs)


class SettingManager(BaseManager):
    # server-version
    PATH_fmt = "apis/management.cattle.io/v3/settings/{name}"
    # "v1/harvesterhci.io.settings/{name}"

    def get(self, name="", *, raw=False):
        return self._get(self.PATH_fmt.format(name=name))


class MgmtClusterManager(BaseManager):
    CREATE_fmt = "v1/provisioning.cattle.io.clusters"
    GET_fmt = "apis/provisioning.cattle.io/v1/namespaces/{ns}/clusters/{uid}"
    DELETE_fmt = "v1/provisioning.cattle.io.clusters/{ns}/{uid}"

    def create_data(self, cluster_name, spec={}, labels={}):
        return {
            "type": "provisioning.cattle.io.cluster",
            "metadata": {
                "namespace": FLEET_DEFAULT_NAMESPACE,
                "labels": labels,
                "name": cluster_name
            },
            "spec": spec
        }

    def get(self, name="", *, raw=False):
        return self._get(self.GET_fmt.format(uid=name, ns=FLEET_DEFAULT_NAMESPACE), raw=raw)

    def create(self, name, spec={}, labels={}, raw=False):
        data = self.create_data(name, spec=spec, labels=labels)
        return self._create(self.CREATE_fmt, json=data, raw=raw)

    def delete(self, name, *, raw=False):
        return self._delete(self.DELETE_fmt.format(uid=name, ns=FLEET_DEFAULT_NAMESPACE))


class ClusterRegistrationTokenManager(BaseManager):
    PATH_fmt = "v3/clusterRegistrationTokens/{uid}:default-token"

    def get(self, name="", *, raw=False):
        return self._get(self.PATH_fmt.format(uid=name), raw=raw)


class CloudCredentialManager(BaseManager):
    PATH_fmt = "v3/cloudcredentials"

    def create_data(self, name, cluster_id, kubeconfig):
        return {
            "type": "provisioning.cattle.io/cloud-credential",
            "metadata": {
                "generateName": "cc-",
                "namespace": FLEET_DEFAULT_NAMESPACE
            },
            "_name": name,
            "annotations": {
                "provisioning.cattle.io/driver": "harvester"
            },
            "harvestercredentialConfig": {
                "clusterType": "imported",
                "clusterId": cluster_id,
                "kubeconfigContent": kubeconfig
            },
            "_type": "provisioning.cattle.io/cloud-credential",
            "name": name
        }

    def create(self, name, cluster_id, kubeconfig, *, raw=False):
        data = self.create_data(name, cluster_id, kubeconfig)
        return self._create(self.PATH_fmt, json=data, raw=raw)

    def list(self, *, raw=False):
        return self._get(self.PATH_fmt, raw=raw)


class KubeConfigManager(BaseManager):
    PATH_fmt = "k8s/clusters/{cluster_id}/v1/harvester/kubeconfig"

    def create_data(self, name):
        return {
            "clusterRoleName": "harvesterhci.io:cloudprovider",
            "namespace": DEFAULT_NAMESPACE,
            "serviceAccountName": name
        }

    def create(self, name, cluster_id, *, raw=True):
        data = self.create_data(name)
        return self._create(self.PATH_fmt.format(cluster_id=cluster_id), json=data, raw=raw)


class SecretManager(BaseManager):
    PATH_fmt = "v1/secrets"

    def create_data(self, name, namespace, data, annotations={}):
        return {
            "type": "secret",
            "metadata": {
                "namespace": namespace,
                "name": name,
                "annotations": annotations
            },
            "data": data
        }

    def create(self, name, namespace, data, annotations={}, *, raw=False):
        data = self.create_data(name, namespace, data, annotations=annotations)
        return self._create(self.PATH_fmt, json=data, raw=raw)


class HarvesterConfigManager(BaseManager):
    PATH_fmt = "v1/rke-machine-config.cattle.io.harvesterconfigs/fleet-default"

    def create_data(self, name, cpu_count, disk_size, memory_size, image_name, network_name,
                    user_data):
        return {
            "cpuCount": cpu_count,
            "diskSize": disk_size,
            "imageName": image_name,
            "memorySize": memory_size,
            "metadata": {
                "name": name,
                "namespace": FLEET_DEFAULT_NAMESPACE,
            },
            "networkName": network_name,
            "sshUser": "ubuntu",
            "userData": user_data,
            "vmNamespace": DEFAULT_NAMESPACE,
            "type": "rke-machine-config.cattle.io.harvesterconfig"
        }

    def create(self, name, cpu_count, disk_size, memory_size, image_name, network_name, user_data,
               *, raw=False):
        data = self.create_data(name, cpu_count, disk_size, memory_size,
                                image_name, network_name, user_data)
        return self._create(self.PATH_fmt, json=data, raw=raw)
