"""
Kafka Consumer for Transaction Streaming
Consumes transactions from Kafka topic and sends to anomaly detection API (FastAPI)
"""

import os
import json
import time
import logging

import requests
from kafka import KafkaConsumer, KafkaProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TransactionConsumer:
    """Kafka consumer for real-time transaction processing."""

    def __init__(
        self,
        kafka_bootstrap_servers: str = "localhost:9092",
        input_topic: str = "transactions",
        output_topic: str = "anomaly_predictions",
        api_url: str = "http://localhost:5000/predict",
        consumer_group: str = "anomaly-detector-group",
    ):
        self.api_url = api_url
        self.batch_size = int(os.getenv("BATCH_SIZE", "10"))
        self.output_topic = output_topic

        self.consumer = KafkaConsumer(
            input_topic,
            bootstrap_servers=kafka_bootstrap_servers,
            group_id=consumer_group,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )

        self.producer = KafkaProducer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )

        logger.info(f"Kafka consumer initialized: {input_topic} -> {output_topic}")

    def start(self):
        logger.info("Starting transaction consumer...")
        batch: list = []

        try:
            for message in self.consumer:
                try:
                    batch.append(message.value)
                    if len(batch) >= self.batch_size:
                        self._process_batch(batch)
                        batch = []
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self._send_to_dlq(message.value, str(e))
        except KeyboardInterrupt:
            logger.info("Consumer stopped by user")
        finally:
            self.consumer.close()
            self.producer.close()

    def _process_batch(self, transactions: list):
        if not transactions:
            return

        fund_batches: dict = {}
        for txn in transactions:
            fund = txn.get("fund_name", "Unknown")
            fund_batches.setdefault(fund, []).append(txn)

        for fund_name, fund_txns in fund_batches.items():
            try:
                response = requests.post(
                    self.api_url,
                    json={"fund_name": fund_name, "transactions": fund_txns},
                    timeout=10,
                )
                if response.status_code == 200:
                    for i, pred in enumerate(response.json()["predictions"]):
                        self.producer.send(
                            self.output_topic,
                            {
                                "transaction": fund_txns[i],
                                "prediction": pred,
                                "timestamp": time.time(),
                            },
                        )
                    logger.info(
                        f"Processed {len(fund_txns)} transactions for {fund_name}"
                    )
                else:
                    logger.error(
                        f"API error: {response.status_code} - {response.text}"
                    )
            except Exception as e:
                logger.error(f"Error processing batch for {fund_name}: {e}")

    def _send_to_dlq(self, message: dict, error: str):
        try:
            self.producer.send(
                "anomaly_detector_dlq",
                {"original_message": message, "error": error, "timestamp": time.time()},
            )
        except Exception as e:
            logger.error(f"Failed to send to DLQ: {e}")


if __name__ == "__main__":
    consumer = TransactionConsumer(
        kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        input_topic=os.getenv("INPUT_TOPIC", "transactions"),
        output_topic=os.getenv("OUTPUT_TOPIC", "anomaly_predictions"),
        api_url=os.getenv("API_URL", "http://localhost:5000/predict"),
    )
    consumer.start()
