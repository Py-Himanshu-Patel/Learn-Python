# Work Queues (Distributing tasks among workers)

In this one we'll create a **Work Queue** that will be used to distribute time-consuming tasks among multiple workers.

The main idea behind **Work Queues** (aka: **Task Queues**) is to avoid doing a resource-intensive task immediately and having to wait for it to complete. Instead we schedule the task to be done later. We encapsulate a task as a message and send it to the queue. A worker process running in the background will pop the tasks and eventually execute the job. When you run many workers the tasks will be shared between them.

We don't have a real-world task, like images to be resized or pdf files to be rendered, so let's fake it by just pretending we're busy - by using the `time.sleep()` function. We'll take the number of dots in the string as its complexity; every dot will account for one second of "work". For example, a fake task described by `Hello...` will take three seconds.

## Sending

Allow arbitrary messages to be sent from the command line. This program will schedule tasks to our work queue.

```python
# new_task.py

import pika
import sys

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel = connection.channel()

channel.queue_declare(queue="hello")
message = " ".join(sys.argv[1:]) or "Hello World!"
channel.basic_publish(exchange="", routing_key="hello", body=message)
print(f" [x] Sent {message}")

connection.close()
```

## Receiving

It needs to fake a second of work for every dot in the message body. It will pop messages from the queue and perform the task.

```python
# worker.py

import pika
import sys
import os
import time


def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()

    channel.queue_declare(queue="hello")

    def callback(ch, method, properties, body):
        print(" [x] Received %r" % body.decode())
        time.sleep(body.count(b'.'))
        print(" [x] Done")

    channel.basic_consume(queue="hello", auto_ack=True, on_message_callback=callback)

    print(" [*] Waiting for messages. To exit press CTRL+C")
    channel.start_consuming()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
```

## Round-robin dispatching

One of the advantages of using a Task Queue is the ability to easily parallelise work. If we are building up a backlog of work, we can just add more workers and that way, scale easily.

First, let's try to run two `worker.py` as (two consumer C1 and C2) scripts at the same time. They will both get messages from the queue, but how exactly? Let's see.

```python
# shell 1
$ python worker.py
 => [*] Waiting for messages. To exit press CTRL+C
 => [x] Received 'First message.'
 => [x] Received 'Third message...'
 => [x] Received 'Fifth message.....'
```

```python
# shell 2
$ python worker.py
 => [*] Waiting for messages. To exit press CTRL+C
 => [x] Received 'Second message..'
 => [x] Received 'Fourth message....'
```

```python
# shell 3
python new_task.py First message.
python new_task.py Second message..
python new_task.py Third message...
python new_task.py Fourth message....
python new_task.py Fifth message.....
```

By default, RabbitMQ will send each message to the next consumer, in sequence **Round Robin**.

## Message acknowledgment

Doing a task can take a few seconds. You may wonder what happens if one of the consumers starts a long task and dies with it only partly done. With our current code once RabbitMQ delivers message to the consumer it immediately marks it for deletion. In this case, if you kill a worker we will lose the message it was just processing. We'll also lose all the messages that were dispatched to this particular worker but were not yet handled.

In order to make sure a message is never lost, RabbitMQ supports message acknowledgments. An ack(nowledgement) is sent back by the consumer to tell RabbitMQ that a particular message had been received, processed and that RabbitMQ is free to delete it.

If a consumer dies (its channel is closed, connection is closed, or TCP connection is lost) without sending an ack, RabbitMQ will understand that a message wasn't processed fully and will re-queue it. If there are other consumers online at the same time, it will then quickly redeliver it to another consumer. That way you can be sure that no message is lost, even if the workers occasionally die.

Manual message acknowledgments are turned on by default. In previous examples we explicitly turned them off via the `auto_ack=True` flag. It's time to remove this flag and send a proper acknowledgment from the worker, once we're done with a task.

```python
def callback(ch, method, properties, body):
    print(" [x] Received %r" % body.decode())
    time.sleep( body.count('.') )
    print(" [x] Done")
    ch.basic_ack(delivery_tag = method.delivery_tag)

channel.basic_consume(queue='hello', on_message_callback=callback)
```

Using this code we can be sure that **_even if you kill a worker using CTRL+C while it was processing a message, nothing will be lost_**. Soon after the worker dies all unacknowledged messages will be redelivered.

Acknowledgement must be sent on the same channel that received the delivery. Attempts to acknowledge using a different channel will result in a channel-level protocol exception. See the doc guide on confirmations to learn more.

### Forgotten acknowledgment

It's a common mistake to miss the `basic_ack`. It's an easy error, but the consequences are serious. Messages will be redelivered when your client quits (which may look like random redelivery), but RabbitMQ will eat more and more memory as it won't be able to release any unacked messages.

In order to debug this kind of mistake you can use `rabbitmqctl` to print the `messages_unacknowledged` field:

```bash
sudo rabbitmqctl list_queues name messages_ready messages_unacknowledged
```

## Message durability

Our tasks can still be lost if RabbitMQ server stops.

When RabbitMQ quits or crashes it will forget the queues and messages unless you tell it not to. Two things are required to make sure that messages aren't lost: we need to mark both the queue and messages as durable.

First, we need to make sure that the queue will survive a RabbitMQ node restart. In order to do so, we need to declare it as durable.

```python
channel.queue_declare(queue='hello', durable=True)
```

Although this command is correct by itself, it won't work in our setup. That's because we've already defined a queue called hello which is not durable. **RabbitMQ doesn't allow you to redefine an existing queue with different parameters and will return** an error to any program that tries to do that. But there is a quick workaround - let's declare a queue with different name, for example `task_queue`:

```python
channel.queue_declare(queue='task_queue', durable=True)
```

This `queue_declare` change needs to be applied to both the producer and consumer code.

At that point we're sure that the `task_queue` queue won't be lost even if RabbitMQ restarts. Now we need to mark our messages as persistent - by supplying a `delivery_mode` property with a value 2.

```python
channel.basic_publish(exchange='',
                      routing_key="task_queue",
                      body=message,
                      properties=pika.BasicProperties(
                         delivery_mode = 2, # make message persistent
                      ))
```

### Note on message persistence

Marking messages as persistent doesn't fully guarantee that a message won't be lost. Although it tells RabbitMQ to save the message to disk, there is still a short time window when RabbitMQ has accepted a message and hasn't saved it yet.

### Fair dispatch

You might have noticed that the dispatching still doesn't work exactly as we want. For example in a situation with two workers, when all odd messages are heavy and even messages are light, one worker will be constantly busy and the other one will do hardly any work. Well, RabbitMQ doesn't know anything about that and will still dispatch messages evenly.

This happens because RabbitMQ just dispatches a message when the message enters the queue. It doesn't look at the number of unacknowledged messages for a consumer. It just blindly dispatches every n-th message to the n-th consumer.

In order to defeat that we can use the `Channel#basic_qos` channel method with the `prefetch_count=1` setting. This uses the `basic.qos` protocol method to tell RabbitMQ not to give more than one message to a worker at a time. Or, in other words, don't dispatch a new message to a worker until it has processed and acknowledged the previous one. Instead, it will dispatch it to the next worker that is not still busy.

```python
# add it consumer before channel.basic_consume() call
channel.basic_qos(prefetch_count=1)
```

#### Note about queue size

If all the workers are busy, your queue can fill up. You will want to keep an eye on that, and maybe add more workers, or use message TTL.

```python
# new_task.py

import pika
import sys

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel = connection.channel()

# channel.queue_declare(queue="hello")
channel.queue_declare(queue="task_queue", durable=True)

message = " ".join(sys.argv[1:]) or "Hello World!"
# channel.basic_publish(exchange="", routing_key="hello", body=message)
channel.basic_publish(
    exchange="",
    routing_key="task_queue",
    body=message,
    properties=pika.BasicProperties(
        delivery_mode=2,  # make message persistent
    ),
)
print(f" [x] Sent {message}")

connection.close()
```

```python
# worker.py

import pika
import sys
import os
import time


def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()

    # channel.queue_declare(queue="hello")
    channel.queue_declare(queue="task_queue", durable=True)

    # def callback(ch, method, properties, body):
    #     print(" [x] Received %r" % body.decode())
    #     time.sleep(body.count(b"."))
    #     print(" [x] Done")

    def callback(ch, method, properties, body):
        print(" [x] Received %r" % body.decode())
        time.sleep( body.count(b'.') )
        print(" [x] Done")
        ch.basic_ack(delivery_tag = method.delivery_tag)

    # channel.basic_consume(queue="hello", auto_ack=True, on_message_callback=callback)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue="task_queue", on_message_callback=callback)

    print(" [*] Waiting for messages. To exit press CTRL+C")
    channel.start_consuming()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
```
