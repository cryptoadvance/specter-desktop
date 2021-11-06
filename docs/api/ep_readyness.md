
# Readyness Endpoint
This endpoint works as heathz-check. See e.g. here:
https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/

Other than the liveness-endpoint, this also checks whether specter is functional from a user-point of view (not only up and listening for requests).

**URL** : `/api/healthz/readyness`

**Method** : `GET`

**Auth required** : No

**Permissions required** : None

### Success Response

**Code** : `200 OK`

**Content examples**

```json
{
  "message": "i am ready"
}
```