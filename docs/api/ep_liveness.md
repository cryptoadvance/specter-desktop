## Liveness Endpoint

This endpoint works as healthz-check. See e.g. here:
https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/

**URL** : `/api/healthz/liveness`

**Method** : `GET`

**Auth required** : No

**Permissions required** : None

### Success Response

**Code** : `200 OK`

**Content examples**

```json
{
  "message": "i am alive"
}
```