# scroxy
Scroxy (scrapper + proxy) is a smart proxy server to hide your scrapper behind
a pool of cloud proxies. When a request arrives, scroxy automatically deploys
a pool of droplets in DigitalOcean. After a timeout, droplets are killed to 
save resources.

## Description
```mermaid
sequenceDiagram

    Actor Client
    participant Server as Scroxy
    participant DigitalOcean as VPS/VDS
    participant Internet

    Client->>+Server: Request

    Server->>DigitalOcean: Create pool
    activate DigitalOcean

    Server->>DigitalOcean: Request
    DigitalOcean->>+Internet: Request
    Internet->>-DigitalOcean: Response
    DigitalOcean->>Server: Response
    
    Server->>-Client: Response

    Client->>+Server: Request

    Server->>DigitalOcean: Request
    DigitalOcean->>+Internet: Request
    Internet->>-DigitalOcean: Response
    DigitalOcean->>Server: Response
    
    Server->>-Client: Response
    

    Server->>DigitalOcean: Timeout. Kill pool
    deactivate DigitalOcean
```