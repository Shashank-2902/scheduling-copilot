# Data: job-shop instances and best-known values

## Instances

`jobshop1.txt` is the unchanged file from the OR-Library:
http://people.brunel.ac.uk/~mastjjb/jeb/orlib/files/jobshop1.txt

It holds 82 job-shop instances contributed to the OR-Library by Dirk C. Mattfeld and
Rob J. M. Vaessens. This project uses 13 of them:

- `ft06`, `ft10`, `ft20`: H. Fisher and G. L. Thompson (1963), "Probabilistic learning
  combinations of local job-shop scheduling rules", in Muth and Thompson (eds.), Industrial
  Scheduling, Prentice Hall, pages 225-251.
- `la01` to `la10`: S. Lawrence (1984), "Resource constrained project scheduling: an
  experimental investigation of heuristic scheduling techniques (Supplement)", Graduate School
  of Industrial Administration, Carnegie-Mellon University.

### File format (checked against the file)

Each instance has a line `instance <name>`, a line of description, a line with the number of
jobs and the number of machines, and then one line per job with pairs of `machine duration`.
Machines are numbered from 0. Every job visits every machine exactly once.

### Licence

OR-Library states that all its material is freely available under the MIT licence,
Copyright (c) 2010 J E Beasley (http://people.brunel.ac.uk/~mastjjb/jeb/orlib/legal.html).
Please cite: J. E. Beasley, "OR-Library: distributing test problems by electronic mail",
Journal of the Operational Research Society 41(11), 1990, pages 1069-1072.

## Best-known values

`best_known.json` holds the best-known makespan of each instance. All 13 are proven optimal.

The values were copied from JSPLIB (https://github.com/tamy0612/JSPLIB, `instances.json`) and then
**checked independently**: every instance was solved with OR-Tools CP-SAT (8 workers, 120 second
limit) and the solver proved the same optimum. The solver also proves the lower bound, so
"best known" and "optimal" are the same number here.

| Instance | Jobs x machines | Best known (optimal) | CP-SAT result | Proven optimal in |
| --- | --- | --- | --- | --- |
| ft06 | 6 x 6 | 55 | 55 | 0.1 s |
| ft10 | 10 x 10 | 930 | 930 | 10.0 s |
| ft20 | 20 x 5 | 1165 | 1165 | 1.5 s |
| la01 | 10 x 5 | 666 | 666 | 0.04 s |
| la02 | 10 x 5 | 655 | 655 | 0.2 s |
| la03 | 10 x 5 | 597 | 597 | 0.1 s |
| la04 | 10 x 5 | 590 | 590 | 0.2 s |
| la05 | 10 x 5 | 593 | 593 | 0.02 s |
| la06 | 15 x 5 | 926 | 926 | 0.03 s |
| la07 | 15 x 5 | 890 | 890 | 0.08 s |
| la08 | 15 x 5 | 863 | 863 | 0.06 s |
| la09 | 15 x 5 | 951 | 951 | 0.05 s |
| la10 | 15 x 5 | 958 | 958 | 0.03 s |

Solve times were measured on a laptop and will differ on other machines. ft10 is the famous hard
one: it stayed open for 25 years after it was published. A modern solver closes it in seconds.

The test suite re-checks ft06 (55), ft10 (930), ft20, la01 and la06 against these values.
