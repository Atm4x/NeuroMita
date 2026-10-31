use std::future::Future;

use tokio_util::sync::CancellationToken;

pub trait Lifecycle: Send + 'static {
    type Error: std::error::Error + Send + Sync + 'static;
    fn run(self, stop: CancellationToken) -> impl Future<Output = Result<(), Self::Error>> + Send;
}
