use std::{
    collections::{HashMap, HashSet},
    io::{self, BufRead},
    sync::Arc,
};

use neuromita::{
    character::CharacterId,
    presentation::ChatPresenter,
    request::{RequestId, RequestOutcome, RequestSnapshot, RequestState},
};
use tokio::sync::mpsc;

pub struct Options {
    pub model: String,
    character: CharacterId,
    message: Option<String>,
    pub listen: std::net::SocketAddr,
}

fn invalid(message: &str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidInput, message)
}

impl Options {
    pub fn parse() -> io::Result<Option<Self>> {
        let mut args = std::env::args().skip(1);
        let mut values = HashMap::new();
        while let Some(argument) = args.next() {
            if argument == "--help" {
                println!(
                    "neuromita --model MODEL --character mita|kind-mita --listen HOST:PORT [--message TEXT]\n\nRequired environment: GEMINI_API_KEY\nNetwork command: test followed by newline\nInteractive commands: /cancel REQUEST_UUID, /character mita|kind-mita, /quit"
                );
                return Ok(None);
            }
            if !matches!(
                argument.as_str(),
                "--model" | "--character" | "--message" | "--listen"
            ) {
                return Err(invalid("unknown argument; use --help"));
            }
            let value = args
                .next()
                .ok_or_else(|| invalid("argument requires a value"))?;
            if values.insert(argument, value).is_some() {
                return Err(invalid("duplicate argument"));
            }
        }
        let model = values
            .remove("--model")
            .ok_or_else(|| invalid("--model is required"))?;
        let character = values
            .remove("--character")
            .ok_or_else(|| invalid("--character is required"))?;
        let character = CharacterId::parse(&character)
            .ok_or_else(|| invalid("unknown character; use mita or kind-mita"))?;
        let listen = values
            .remove("--listen")
            .ok_or_else(|| invalid("--listen is required"))?
            .parse()
            .map_err(|_| invalid("invalid listen address"))?;
        Ok(Some(Self {
            model,
            character,
            message: values.remove("--message"),
            listen,
        }))
    }
}

fn input() -> mpsc::Receiver<io::Result<String>> {
    let (send, receive) = mpsc::channel(16);
    std::thread::spawn(move || {
        for line in io::stdin().lock().lines() {
            if send.blocking_send(line).is_err() {
                break;
            }
        }
    });
    receive
}

fn display(snapshot: &RequestSnapshot) {
    let id = snapshot.metadata.id;
    let character = snapshot.metadata.character_id;
    match &snapshot.state {
        RequestState::Pending => println!("[{id}] {character}: pending"),
        RequestState::Processing(_) => println!("[{id}] {character}: processing"),
        RequestState::Cancelled => println!("[{id}] {character}: cancelled"),
        RequestState::Finished(RequestOutcome::Success(response)) => {
            println!("[{id}] {character}: success\n{}", response.text)
        }
        RequestState::Finished(RequestOutcome::TextGenerationFailed(error)) => {
            eprintln!("[{id}] {character}: text generation failed: {error}")
        }
        RequestState::Finished(RequestOutcome::InternalError(error)) => {
            eprintln!("[{id}] {character}: internal error: {error}")
        }
        RequestState::Finished(RequestOutcome::VoiceGenerationFailed { response, error }) => {
            eprintln!(
                "[{id}] {character}: voice failed: {error}\n{}",
                response.text
            );
        }
    }
}

pub async fn run(presenter: &ChatPresenter, options: Options) -> io::Result<()> {
    let mut character = options.character;
    let mut updates = presenter.observe();
    let mut printed: HashMap<RequestId, u64> = HashMap::new();
    let mut pending = HashSet::new();
    let mut failed = false;
    let mut eof = options.message.is_some();
    let mut lines = if eof { None } else { Some(input()) };
    if let Some(message) = options.message {
        let handle = presenter
            .reply(character, message)
            .map_err(|error| invalid(&error.to_string()))?;
        pending.insert(handle.id());
    } else {
        println!(
            "Gemini model: {}. Character: {character}. Enter a message; /quit to exit.",
            options.model
        );
    }
    loop {
        let model = { Arc::clone(&updates.borrow_and_update()) };
        if let Some(error) = &model.discovery_error {
            eprintln!("Observation warning: {error}");
        }
        for row in &model.requests {
            let id = row.metadata.id;
            if printed
                .get(&id)
                .is_none_or(|revision| *revision < row.snapshot.revision)
            {
                display(&row.snapshot);
                printed.insert(id, row.snapshot.revision);
            }
            if row.snapshot.state.is_terminal()
                && pending.remove(&id)
                && !matches!(
                    row.snapshot.state,
                    RequestState::Finished(RequestOutcome::Success(_))
                )
            {
                failed = true;
            }
            if let Some(error) = &row.observation_error {
                return Err(io::Error::other(error.to_string()));
            }
        }
        if eof && pending.is_empty() {
            return if failed {
                Err(io::Error::other("one or more requests did not succeed"))
            } else {
                Ok(())
            };
        }
        tokio::select! {
            signal = tokio::signal::ctrl_c() => { signal?; return Ok(()); }
            changed = updates.changed() => {
                changed.map_err(|_| io::Error::other("presenter stopped"))?;
            }
            line = async { lines.as_mut().expect("input enabled").recv().await }, if lines.is_some() => {
                match line {
                    None => { eof = true; lines = None; }
                    Some(Err(error)) => return Err(error),
                    Some(Ok(line)) => {
                        if line == "/quit" { return Ok(()); }
                        if let Some(value) = line.strip_prefix("/character ") {
                            match CharacterId::parse(value) {
                                Some(id) => { character = id; println!("Character: {id}"); }
                                None => eprintln!("Unknown character"),
                            }
                        } else if let Some(value) = line.strip_prefix("/cancel ") {
                            match uuid::Uuid::parse_str(value) {
                                Ok(id) => match presenter.cancel(RequestId(id)) {
                                    Ok(result) => println!("Cancel: {result:?}"),
                                    Err(error) => eprintln!("{error}"),
                                }
                                Err(_) => eprintln!("Invalid request UUID"),
                            }
                        } else {
                            match presenter.reply(character, line) {
                                Ok(handle) => { println!("Accepted: {}", handle.id()); pending.insert(handle.id()); }
                                Err(error) => eprintln!("{error}"),
                            }
                        }
                    }
                }
            }
        }
    }
}
