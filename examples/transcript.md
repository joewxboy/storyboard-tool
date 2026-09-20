# Why your edge box keeps falling over

## The problem

Everyone builds the same first edge deployment. One box, one container, a cron
job that restarts it when it dies, and a dashboard nobody looks at. It works
right up until the moment the container comes back healthy but wrong, and the
cron job happily keeps it that way for three weeks.

## What is actually wrong

A restart is not a remediation. The box came back, the process is running, the
port answers — and the model it is serving never finished loading. Liveness
checks that only look for a listening socket will tell you everything is fine.

## The fix

Health has to mean something specific to the workload. For an inference
service that means: the model file is loaded, a sample prompt returns in under
a second, and the last ten requests did not error. Anything less is a socket
check wearing a costume.

## What to do on Monday

Write the check that a human would run to decide the box is healthy, put it
behind an endpoint, and let the supervisor read that instead of the port. Then
delete the cron job.
