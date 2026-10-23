from locust import HttpUser, task, constant


class Trader(HttpUser):
    wait_time = constant(0)  # no pause, so you find the real limit

    @task(10)
    def stocks(self):
        self.client.get("/api/stocks")

    @task(5)
    def portfolio(self):
        self.client.get("/api/portfolio")

    @task(2)
    def trades(self):
        self.client.get("/api/trades")

    @task(2)
    def buy_then_sell(self):
        # Buy 1 share; sell it only if the buy worked, so holdings and cash stay balanced
        with self.client.post(
            "/api/trade/buy",
            json={"symbol": "TCS", "quantity": 1},
            catch_response=True,
        ) as buy:
            if buy.status_code != 200:
                buy.failure(f"buy failed: {buy.status_code} {buy.text}")
                return

        with self.client.post(
            "/api/trade/sell",
            json={"symbol": "TCS", "quantity": 1},
            catch_response=True,
        ) as sell:
            if sell.status_code != 200:
                sell.failure(f"sell failed: {sell.status_code} {sell.text}")
