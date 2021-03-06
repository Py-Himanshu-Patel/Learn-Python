# Topic

`fanout` exchange only capable of dummy broadcasting, and `direct` have a feature of selectively receiving the logs. but it still has limitations - it can't do routing based on multiple criteria.

In our logging system we might want to subscribe to not only logs based on **severity**, but also based on the **source which emitted the log**. Like routes logs based on both **severity** `(info/warn/crit...)` and facility `(auth/cron/kern...)`. To implement that in our logging system we need to learn about a more complex `topic` exchange.

## Topic exchange

Messages sent to a `topic` exchange can't have an arbitrary `routing_key` - it must be a list of words, delimited by dots. The words can be anything, but usually they specify some features connected to the message. A few valid routing key examples: `stock.usd.nyse`, `nyse.vmw`, `quick.orange.rabbit`. There can be as many words in the routing key as you like, up to the limit of 255 bytes.

The binding key must also be in the same form. The logic behind the topic exchange is similar to a direct one - a message sent with a particular routing key will be delivered to all the queues that are bound with a matching binding key. However there are two important special cases for binding keys:

- `*` (star) can substitute for exactly one word.
- `#` (hash) can substitute for zero or more words.

Let suppose the messages will be sent with a routing key that consists of three words (two dots). The first word in the routing key will describe a celerity, second a colour and third a species: `<celerity>.<colour>.<species>`.

We created three bindings:

- Q1 is bound with binding key `*.orange.*`
- Q2 with `*.*.rabbit` and `lazy.#`.

These bindings can be summarised as:

- Q1 is interested in all the orange animals.
- Q2 wants to hear everything about rabbits, and everything about lazy animals.

A message with a routing key set to `quick.orange.rabbit` will be delivered to both queues. On the other hand `quick.orange.fox` will only go to the first queue. `lazy.pink.rabbit` will be delivered to the second queue only once, even though it matches two bindings. `quick.brown.fox` doesn't match any binding so it will be discarded.

What happens if we break our contract and send a message with one or four words, like `orange` or `quick.orange.male.rabbit`? Well, **these messages won't match any bindings and will be lost**.

On the other hand `lazy.orange.male.rabbit`, even though it has four words, will match the last binding and will be delivered to the second queue.

### Topic exchange is powerful and can behave like other exchanges.

- When a queue is bound with `#` (hash) binding key - it will receive all the messages, regardless of the routing key - like in fanout exchange.

- When special characters `*` (star) and `#` (hash) aren't used in bindings, the topic exchange will behave just like a direct one.

## Putting it all together

We'll start off with a working assumption that the routing keys of logs will have two words: `<facility>.<severity>`.

```python
import pika
import sys

connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
channel = connection.channel()

# make a topic exchange
channel.exchange_declare(exchange="topic_logs", exchange_type="topic")
# get the command line input
routing_key = sys.argv[1] if len(sys.argv) > 2 else "anonymous.info"
# get message from command line input
message = " ".join(sys.argv[2:]) or "Hello World!"

# publish the log on a particular topic given in routing_key
channel.basic_publish(exchange="topic_logs", routing_key=routing_key, body=message)

print(" [x] Sent %r:%r" % (routing_key, message))
connection.close()
```

```python
import pika
import sys

connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
channel = connection.channel()

# declare the topic exchange
channel.exchange_declare(exchange="topic_logs", exchange_type="topic")
# declare the queue with random name
result = channel.queue_declare("", exclusive=True)
queue_name = result.method.queue

# get the binding key which is the (. seperated )topic name
binding_keys = sys.argv[1:]
if not binding_keys:
    sys.stderr.write("Usage: %s [binding_key]...\n" % sys.argv[0])
    sys.exit(1)

# make queue bind to a particular topic (provided it as routing_key)
for binding_key in binding_keys:
    channel.queue_bind(exchange="topic_logs", queue=queue_name, routing_key=binding_key)

print(" [*] Waiting for logs. To exit press CTRL+C")


def callback(ch, method, properties, body):
    print(" [x] %r:%r" % (method.routing_key, body))


channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
channel.start_consuming()
```

To receive all the logs run:

```bash
python receive_logs_topic.py "#"
```

To receive all logs from the facility `kern`:

```bash
python receive_logs_topic.py "kern.*"
```

Or if you want to hear only about `critical` logs:

```bash
python receive_logs_topic.py "*.critical"
```

You can create multiple bindings:

```bash
python receive_logs_topic.py "kern.*" "*.critical"
```

And to emit a log with a routing key `kern.critical` type:

```bash
python emit_log_topic.py kern.critical A critical kernel error
```

Have fun playing with these programs. Note that the code doesn't make any assumption about the routing or binding keys, you may want to play with more than two routing key parameters.
