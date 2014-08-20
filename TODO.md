# OpenCache Roadmap #

Last Edited: 19/03/2014

Comment: Updated

## Priority Features ##

### Load Balancing and Reporting ###
_OpenCache Application_

Balance traffic between caches using network and node load. Report node load back to controller when threshold reached.

### OpenCache Console ###
_In progress_

Complete rewrite of OpenCache Console using Flask. Update to use most recent version of API. 

### MPD Parser ###
_OpenCache Application_

An application that takes an MPEG-DASH manifest file, and utilises the relevant OpenCache commands to add the content relevant content.

## Planned Features ##

### HTTP Byte-Range Support ###
Implement the ability to cache partial file requests without the need to fetch the whole file. Store those ranges in such a way that they can be served incrementally and eventually form the full object (if possible). See: [http://www.w3.org/ProtOpenCacheols/rfc2616/rfc2616-sec14.html](http://www.w3.org/ProtOpenCacheols/rfc2616/rfc2616-sec14.html).

### CDNi interface ###
Implement a CDNi interface to allow OpenCache deployments to interface with existing CDNs.

### OpenCache Topology ###
Present network topology (including OpenCache nodes) to user. OpenCache nodes might describe the popularity of content already located on there (which could be used to infer audience). This should help inform cache content and placement decisions. This information should be displayed in the console, but also in a well-defined JSON format, so that OpenCache applications can use it. Should include OpenCache nodes and the switches between them.

### OpenCache Discovery Protocol ###
Define OF rules which show the ‘nearest’ OF switch to a node.

### Feature Complete OpenCache Expressions ###
Fully implement regex like expressions. Consider rule clashes.

### Node Labelling ###

Label and classify nodes (a la Puppet), so that they can be addressed as a group.