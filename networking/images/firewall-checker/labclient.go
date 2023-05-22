package main

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"os"
	"strings"
)

const unixSocketPath = "/var/run/quirck.sock"
const submitRequestTemplate = "/done?user_id=%s&chapter=%s&task=%s"

type LabClient interface {
	Submit() error
}

type labClientImpl struct {
	chapter string
	task    string
	user_id string
	client  http.Client
}

func (c *labClientImpl) Submit() error {
	url := fmt.Sprintf(submitRequestTemplate, c.user_id, c.chapter, c.task)
	_, err := c.client.Post("http://unix"+url, "application/octet-stream", strings.NewReader(""))
	if err != nil {
		return err
	}
	return nil
}

func NewLabClient() LabClient {
	return &labClientImpl{
		chapter: os.Getenv("CHAPTER"),
		task:    os.Getenv("TASK"),
		user_id: os.Getenv("USER_ID"),
		client: http.Client{
			Transport: &http.Transport{
				DialContext: func(_ context.Context, _, _ string) (net.Conn, error) {
					return net.Dial("unix", unixSocketPath)
				},
			},
		},
	}
}
