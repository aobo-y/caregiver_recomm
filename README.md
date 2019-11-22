# caregiver_recomm

## Usage

```python
from caregiver_recomm import Recommender

recomm = Recommender()
recomm.dispatch(speaker_id, evt)
```

### Recommender(evt_dim=4)

- **evt_dim**: Event dimensions, default `4`
- **mock**: Simulate the user interaction, default `False`
- **server_config**: Remote server configuration, default `None`
  - **client_id**: client id
  - **url**: server url

### dispatch(speaker_id, evt)

- **speacker_id**:
- **evt**: numpy array or python list
