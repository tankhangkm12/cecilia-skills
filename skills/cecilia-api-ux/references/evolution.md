# Evolution — changing the contract without breaking consumers

`apikit.py diff old.yaml new.yaml` lists breaking changes found in the specs; confirm each against code.

| Change | Breaking? | Safe path |
|---|---|---|
| remove endpoint / response field / enum value | yes | deprecate with date, keep for one release window, then remove in a new version |
| rename field | yes | add the new name, keep the old, deprecate |
| change type/format (number → string) | yes | new field or new version |
| add required request field / parameter | yes | make it optional with a default, or new version |
| narrow validation (shorter max length) | yes | only with a version or data proof no client sends it |
| add optional field / endpoint / enum value | no* | *clients must tolerate unknown fields and enum values — state it in the contract |
| change default sort/pagination | behaviourally yes | new parameter, keep the default |

Every breaking change in the report names: who breaks (which clients, which versions), migration path,
dates, and whether Cecilia must decide (always, for a public contract).
