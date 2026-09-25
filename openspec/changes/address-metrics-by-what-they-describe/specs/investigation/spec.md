## ADDED Requirements

### Requirement: An address opens a view of what the retrieval was about
Where the system composes an address for a retrieval, that address SHALL open
a view of the subject the retrieval concerned. The system SHALL NOT address a
retrieval at a view of a different subject on the grounds that both belong to
the same service: a service has many views, and one showing nothing about the
finding is indistinguishable, to the reader who opens it, from one showing
that nothing happened.

Which view a retrieval is addressed at SHALL be decided by what the retrieval
fetched, not by which specialist asked for it. Two specialists calling the same
tool about the same service retrieved the same kind of thing, and the reader
following either address is going to look at the same view.

Where the subject of a retrieval cannot be recovered from what was retrieved
or from what the tool was asked, the system SHALL give no address at all. No
address is visibly nothing; an address scoped to the wrong subject is not.

A view that has not been confirmed to open against a real account SHALL NOT be
used as an address. An unconfirmed view is a guess about the platform, and the
cost of the guess is paid by the reader who follows it.

#### Scenario: A resource metric is addressed
- **WHEN** a finding cites a retrieval of a metric describing the resources a
  service runs on
- **THEN** the address opens a view of that metric, not a view of the service's
  request traffic

#### Scenario: The same tool, a different specialist
- **WHEN** two specialists each retrieve a metric for the same service using
  the same tool
- **THEN** both retrievals are addressed at the same kind of view, because both
  fetched the same kind of thing

#### Scenario: The subject cannot be read
- **WHEN** a retrieval's subject cannot be recovered from what was retrieved or
  from what the tool was asked
- **THEN** the retrieval carries no address, and is still reported with what it
  returned

#### Scenario: A view that has not been confirmed
- **WHEN** a view proposed as an address does not open against a real account
- **THEN** it is not used, and retrievals of that kind carry no address rather
  than an unconfirmed one
